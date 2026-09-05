"""
MerchantMesh - LangGraph Trust & Safety Agent
Orchestrates:
1. Strict Code-Level Floor Price and Buyer Spending Cap Guardrails
2. Human-in-the-Loop Merchant Order Confirmation (Y / N / TIMEOUT)
3. 15-Minute Expiring Razorpay Payment Link Generation via Razorpay Client & MCP Tools
4. Autonomous Failure Recovery: Dispatches Discovery Agent to find ranked alternative products
   when a merchant rejects or times out
5. Full SQLite Audit Logging and Order Lifecycle Management
"""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from agents.discovery_agent import run_discovery_agent
from core.config import DB_PATH, generate_execution_provenance
from core.razorpay_client import razorpay_client
from core.trust_engine import (
    _verify_and_lock_stock_tx,
    check_buyer_trust,
    penalize_merchant_on_failure,
    verify_spending_cap,
    verify_stock_availability,
    verify_transaction_price_floor,
)
from data.database import get_db_connection

load_dotenv()


class TrustAgentState(TypedDict):
    order_id: str
    negotiation_id: str | None
    product_id: str
    merchant_id: str
    buyer_id: str
    buyer_phone: str
    buyer_name: str
    agreed_price: int
    quantity: int
    buyer_max_budget: int | None
    merchant_response: str  # "Y", "N", "TIMEOUT"
    product: dict[str, Any] | None
    merchant: dict[str, Any] | None
    buyer_trust: dict[str, Any] | None
    guardrail_status: str  # "PASSED", "REJECTED_PRICE_FLOOR", "REJECTED_SPENDING_CAP", "REJECTED_STOCK_UNAVAILABLE"
    guardrail_reason: str
    payment_link_id: str | None
    payment_link_url: str | None
    expires_at: str | None
    alternatives: list[dict[str, Any]]
    status: str  # "INITIATED", "PAYMENT_LINK_GENERATED", "REJECTED_BY_MERCHANT", "TIMEOUT_EXPIRED", "GUARDRAIL_VIOLATION"
    message: str
    audit_reasoning: str


# ==========================================
# 1. STATE GRAPH NODES
# ==========================================

def init_and_verify_guardrails_node(state: TrustAgentState) -> dict[str, Any]:
    """
    Node 1: Loads database entities and enforces strict code-level guardrails:
    - Price Floor constraint (Code-level guarantee against sub-floor sales)
    - Spending Cap & safety limit verification
    - Stock availability & prohibited goods filter
    - Buyer risk assessment (return fraud prevention)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Fetch Product
        cursor.execute("SELECT * FROM products WHERE id = ?", (state["product_id"],))
        prod_row = cursor.fetchone()
        if not prod_row:
            return {
                "guardrail_status": "REJECTED_STOCK_UNAVAILABLE",
                "guardrail_reason": f"Product '{state['product_id']}' does not exist in catalog.",
                "status": "GUARDRAIL_VIOLATION"
            }
        product = dict(prod_row)

        # 2. Fetch Merchant
        merchant_id = product["merchant_id"]
        cursor.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
        merch_row = cursor.fetchone()
        merchant = dict(merch_row) if merch_row else {"id": merchant_id, "name": "Local Seller", "reliability_score": 5.0}

        # 3. Fetch Buyer Trust & ENFORCE HARD GATE
        buyer_id = state.get("buyer_id", "b1")
        buyer_trust = check_buyer_trust(buyer_id)
        if not buyer_trust.get("is_safe", True):
            return {
                "product": product,
                "merchant": merchant,
                "merchant_id": merchant_id,
                "buyer_trust": buyer_trust,
                "guardrail_status": "REJECTED_BUYER_TRUST",
                "guardrail_reason": buyer_trust.get("warning", "Buyer flagged for excessive return risk (>40%)."),
                "status": "GUARDRAIL_VIOLATION"
            }

        quantity = max(1, state.get("quantity", 1))
        agreed_price = state.get("agreed_price", product["listed_price"])

        # 4. STRICT CODE-LEVEL FLOOR CHECK
        floor_passed, floor_reason, floor_details = verify_transaction_price_floor(
            product_id=state["product_id"],
            proposed_price=agreed_price,
            quantity=quantity
        )
        if not floor_passed:
            return {
                "product": product,
                "merchant": merchant,
                "merchant_id": merchant_id,
                "buyer_trust": buyer_trust,
                "guardrail_status": "REJECTED_PRICE_FLOOR",
                "guardrail_reason": floor_reason,
                "status": "GUARDRAIL_VIOLATION"
            }

        # 5. SPENDING CAP CHECK
        budget_passed, budget_reason = verify_spending_cap(
            buyer_id=buyer_id,
            amount=agreed_price,
            max_budget=state.get("buyer_max_budget")
        )
        if not budget_passed:
            return {
                "product": product,
                "merchant": merchant,
                "merchant_id": merchant_id,
                "buyer_trust": buyer_trust,
                "guardrail_status": "REJECTED_SPENDING_CAP",
                "guardrail_reason": budget_reason,
                "status": "GUARDRAIL_VIOLATION"
            }

        # 6. STOCK AVAILABILITY CHECK
        stock_passed, avail_stock, stock_reason = verify_stock_availability(
            product_id=state["product_id"],
            requested_qty=quantity
        )
        if not stock_passed:
            return {
                "product": product,
                "merchant": merchant,
                "merchant_id": merchant_id,
                "buyer_trust": buyer_trust,
                "guardrail_status": "REJECTED_STOCK_UNAVAILABLE",
                "guardrail_reason": stock_reason,
                "status": "GUARDRAIL_VIOLATION"
            }

        return {
            "product": product,
            "merchant": merchant,
            "merchant_id": merchant_id,
            "buyer_trust": buyer_trust,
            "guardrail_status": "PASSED",
            "guardrail_reason": "All safety checks and price floor constraints passed successfully."
        }
    finally:
        conn.close()


def merchant_confirmation_node(state: TrustAgentState) -> dict[str, Any]:
    """
    Node 2: Evaluates Human-in-the-Loop Merchant Response ('Y' / 'N' / 'TIMEOUT' / 'AWAITING_MERCHANT').
    Does NOT default missing responses to 'Y'. Missing/unknown response stays in AWAITING_MERCHANT.
    """
    resp = (state.get("merchant_response") or "").strip().upper()
    product_id = state["product_id"]
    merchant_id = state.get("merchant_id") or ((state.get("product") or {}).get("merchant_id", "m1"))

    if resp == "Y":
        return {
            "merchant_response": "Y",
            "status": "MERCHANT_CONFIRMED"
        }
    elif resp == "N":
        penalize_merchant_on_failure(product_id, merchant_id, reason="REJECTED_OUT_OF_STOCK")
        return {
            "merchant_response": "N",
            "status": "REJECTED_BY_MERCHANT"
        }
    elif resp == "TIMEOUT":
        penalize_merchant_on_failure(product_id, merchant_id, reason="MERCHANT_TIMEOUT")
        return {
            "merchant_response": "TIMEOUT",
            "status": "TIMEOUT_EXPIRED"
        }
    else:
        return {
            "merchant_response": "AWAITING",
            "status": "AWAITING_MERCHANT"
        }


def generate_payment_link_node(state: TrustAgentState) -> dict[str, Any]:
    """
    Node 3: Creates a 15-minute expiring Razorpay payment link via two-phase atomic reservation:
    Phase 1 (DB Lock): BEGIN IMMEDIATE -> reserve stock -> transition order to PENDING_PAYMENT -> COMMIT.
    Phase 2 (Network I/O): Call razorpay_client.create_payment_link() outside DB lock.
    Phase 3 (Post-Network): Update order with link details or cleanly release reservation on gateway failure.
    """
    order_id = state.get("order_id") or f"ord_{uuid.uuid4().hex[:10]}"
    amount = state.get("agreed_price", 1000)
    quantity = max(1, state.get("quantity", 1))
    product_id = state["product_id"]
    merchant_id = state.get("merchant_id") or "m1"
    buyer_id = state.get("buyer_id", "b1")
    product_name = (state.get("product") or {}).get("product_name", "Product")
    merchant_name = (state.get("merchant") or {}).get("name", "Merchant")
    buyer_name = state.get("buyer_name", "Customer")
    buyer_phone = state.get("buyer_phone", "9876543210")
    negotiation_id = state.get("negotiation_id")

    from datetime import timezone
    expires_at_dt = datetime.now(timezone.utc) + timedelta(minutes=15)
    expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")
    res_id = f"res_{uuid.uuid4().hex[:10]}"

    # Phase 1: Atomic Database Reservation (Inside SQLite BEGIN IMMEDIATE)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        # Atomic Re-verification of stock availability inside the active write lock
        stock_ok, _, stock_msg = _verify_and_lock_stock_tx(cursor, product_id, quantity)
        if not stock_ok:
            conn.rollback()
            return {
                "order_id": order_id,
                "status": "GUARDRAIL_VIOLATION",
                "guardrail_status": "REJECTED_STOCK_UNAVAILABLE",
                "guardrail_reason": stock_msg,
                "message": f"❌ Stock contention: {stock_msg}",
                "audit_reasoning": f"Stock reservation blocked for order {order_id}: {stock_msg}"
            }

        # Create/Update order in PENDING_PAYMENT with explicit conflict handling
        cursor.execute("""
            INSERT INTO orders (
                id, negotiation_id, product_id, merchant_id, buyer_id, 
                quantity, amount, payment_status, settlement_status, 
                merchant_confirmed, expires_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', 1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                payment_status = 'PENDING_PAYMENT',
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
            WHERE orders.payment_status NOT IN ('PAID', 'SETTLED')
        """, (order_id, negotiation_id, product_id, merchant_id, buyer_id, quantity, amount, expires_at_str))

        # Insert active reservation
        cursor.execute("""
            INSERT INTO stock_reservations (
                id, order_id, product_id, quantity, status, expires_at
            ) VALUES (?, ?, ?, ?, 'ACTIVE', ?)
            ON CONFLICT(order_id) DO UPDATE SET
                status = 'ACTIVE',
                expires_at = excluded.expires_at
            WHERE stock_reservations.status != 'CONSUMED'
        """, (res_id, order_id, product_id, quantity, expires_at_str))

        conn.commit()
    finally:
        conn.close()

    # Phase 2: Call Razorpay API outside the SQLite write lock
    description = f"MerchantMesh Order: {quantity}x {product_name} from {merchant_name}"
    try:
        res = razorpay_client.create_payment_link(
            amount_inr=amount,
            customer_phone=buyer_phone,
            customer_name=buyer_name,
            description=description,
            reference_id=order_id,
            expire_in_mins=15,
            notes={
                "product_id": product_id,
                "merchant_id": merchant_id,
                "negotiation_id": negotiation_id
            }
        )
    except Exception as e:
        res = {"status": "FAILED", "error": str(e), "is_simulated": False}

    # Phase 3: Post-network persistence & rollback handling
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        if res.get("status") == "FAILED":
            err_msg = str(res.get("error") or "").lower()
            is_timeout = "timeout" in err_msg or "timed out" in err_msg or "connection" in err_msg or "gateway" in err_msg

            if is_timeout:
                # Gateway network timeout: preserve reservation and flag for reconciliation
                cursor.execute("""
                    UPDATE orders 
                    SET payment_status = 'PAYMENT_LINK_RECONCILIATION_REQUIRED', updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (order_id,))
                conn.commit()
                return {
                    "order_id": order_id,
                    "status": "PAYMENT_LINK_RECONCILIATION_REQUIRED",
                    "message": f"Gateway timeout during link creation: {res.get('error')}. Order placed in reconciliation state.",
                    "audit_reasoning": f"Gateway timeout during payment link creation for order {order_id}. Preserving stock reservation for webhook reconciliation."
                }
            else:
                # Deterministic failure (e.g. invalid auth): release reservation and cancel
                cursor.execute("UPDATE stock_reservations SET status = 'EXPIRED' WHERE order_id = ?", (order_id,))
                cursor.execute("UPDATE orders SET payment_status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
                conn.commit()
                return {
                    "order_id": order_id,
                    "status": "PAYMENT_LINK_FAILED",
                    "message": f"Payment link creation failed: {res.get('error')}. Reservation released.",
                    "audit_reasoning": f"Razorpay link creation failed for order {order_id}. Reservation released."
                }

        plink_id = res["payment_link_id"]
        plink_url = res["payment_link_url"]
        expires_at = res["expires_at"]

        # Persist payment link identifiers
        cursor.execute("""
            UPDATE orders 
            SET payment_link_id = ?, payment_link_url = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (plink_id, plink_url, order_id))
        conn.commit()
    finally:
        conn.close()

    msg = (
        f"✅ Seller {merchant_name} confirmed stock & availability! 🎉\n"
        f"🛍️ Order ID: {order_id}\n"
        f"💰 Total Amount: ₹{amount:,} ({quantity} item(s))\n"
        f"🔗 Pay via Razorpay: {plink_url}\n"
        f"⏳ Note: This payment link is valid for 15 minutes (expires at {expires_at[11:19]}). "
        f"Inventory is reserved and payment link is bound to order with webhook verification."
    )

    reasoning = (
        f"Order {order_id} confirmed by merchant {merchant_name}. "
        f"Committed atomic stock reservation and generated 15-min Razorpay payment link {plink_id} for ₹{amount:,}."
    )

    return {
        "order_id": order_id,
        "payment_link_id": plink_id,
        "payment_link_url": plink_url,
        "expires_at": expires_at,
        "status": "PAYMENT_LINK_GENERATED",
        "message": msg,
        "audit_reasoning": reasoning
    }


def handle_failure_node(state: TrustAgentState) -> dict[str, Any]:
    """
    Node 4: Failure Handler with AGENTIC ALTERNATIVE RECOVERY.
    - If Price Floor Guardrail violated: Hard rejects with mathematical margin reasoning.
    - If Buyer Trust violated: Hard blocks before any order or reservation creation.
    - If Merchant says 'N' (Out of stock) or TIMEOUT: Automatically triggers Discovery Agent
      to retrieve top 3 alternative matching products from other reliable sellers.
    """
    status = state.get("status")
    guardrail_status = state.get("guardrail_status")
    product_name = (state.get("product") or {}).get("product_name", "item")
    category = (state.get("product") or {}).get("category", "")
    merchant_name = (state.get("merchant") or {}).get("name", "Seller")

    alternatives: list[dict[str, Any]] = []

    # 1. Buyer Trust Violation Hard Block
    if guardrail_status == "REJECTED_BUYER_TRUST":
        reason = state.get("guardrail_reason", "High return fraud risk detected.")
        msg = (
            f"🛑 Transaction Blocked: {reason}\n"
            f"Payment links cannot be generated for accounts exceeding platform risk thresholds."
        )
        return {
            "status": "GUARDRAIL_VIOLATION",
            "message": msg,
            "alternatives": [],
            "audit_reasoning": f"Buyer trust guardrail blocked transaction: {reason}"
        }

    # 2. Price Floor Violation Rejection
    if guardrail_status == "REJECTED_PRICE_FLOOR":
        reason = state.get("guardrail_reason", "Price is below minimum floor.")
        msg = (
            f"🛑 Transaction Blocked by Trust Guardrail: {reason}\n"
            f"To protect merchant profitability and prevent hallucinated pricing, transactions below the seller floor price cannot be finalized."
        )
        return {
            "status": "GUARDRAIL_VIOLATION",
            "message": msg,
            "alternatives": [],
            "audit_reasoning": f"Code guardrail blocked transaction: {reason}"
        }

    # 3. Spending Cap Violation
    if guardrail_status == "REJECTED_SPENDING_CAP":
        reason = state.get("guardrail_reason", "Amount exceeds budget cap.")
        return {
            "status": "GUARDRAIL_VIOLATION",
            "message": f"🛑 Transaction Blocked: {reason}",
            "alternatives": [],
            "audit_reasoning": f"Code guardrail blocked transaction: {reason}"
        }

    # 4. Merchant Rejection ('N') or Timeout -> Discover Alternatives
    search_query = f"{product_name} {category}".strip()
    try:
        disc_result = run_discovery_agent(query=search_query, buyer_id=state.get("buyer_id"))
        all_recs = disc_result.get("ranked_products", [])
        # Filter out the currently failing product
        alternatives = [p for p in all_recs if p.get("id") != state.get("product_id")][:3]
    except Exception as e:
        print(f"⚠️ Discovery Agent alternative search notice: {e}")
        alternatives = []

    if status == "REJECTED_BY_MERCHANT":
        msg = (
            f"❌ Seller {merchant_name} reported that '{product_name}' is currently unavailable or out of stock.\n"
            f"💡 Agentic Recovery: I searched the live catalog and found {len(alternatives)} great alternative recommendations from verified sellers for you!"
        )
        reasoning = (
            f"Merchant {merchant_name} rejected order for product {state.get('product_id')} (Out of stock). "
            f"Triggered Discovery Agent and retrieved {len(alternatives)} alternative products for the buyer."
        )
    elif status == "TIMEOUT_EXPIRED":
        msg = (
            f"⏱️ Seller {merchant_name} did not respond within the confirmation window.\n"
            f"💡 Agentic Recovery: To save your time, I found {len(alternatives)} active, responsive alternative options matching your search!"
        )
        reasoning = (
            f"Merchant {merchant_name} timed out on product {state.get('product_id')}. "
            f"Confidence score decayed. Retried discovery and presented {len(alternatives)} alternative products."
        )
    else:
        msg = f"Order could not be completed: {state.get('guardrail_reason', 'Validation failed.')}"
        reasoning = f"Order failed with status {status}."

    return {
        "message": msg,
        "alternatives": alternatives,
        "audit_reasoning": reasoning
    }


def persist_order_and_audit_node(state: TrustAgentState) -> dict[str, Any]:
    """
    Node 5: Persists order into SQLite 'orders' table and logs all compliance,
    security, and transaction reasoning into 'audit_log'.
    Guardrail violations create zero orders and zero stock reservations.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        order_id = state.get("order_id") or f"ord_{uuid.uuid4().hex[:10]}"
        status = state.get("status", "COMPLETED")
        
        # Hard invariant: Guardrail violations MUST NOT create database orders or reservations
        if status == "GUARDRAIL_VIOLATION":
            audit_action = f"GUARDRAIL_{state.get('guardrail_status', 'VIOLATION')}"
            cursor.execute(
                "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                (audit_action, "TrustAgent", state.get("audit_reasoning", f"Guardrail blocked order {order_id}."))
            )
            conn.commit()
            return {}

        payment_status_map = {
            "PAYMENT_LINK_GENERATED": "PENDING_PAYMENT",
            "PAYMENT_LINK_FAILED": "CANCELLED",
            "REJECTED_BY_MERCHANT": "REJECTED_BY_MERCHANT",
            "TIMEOUT_EXPIRED": "TIMEOUT_EXPIRED"
        }
        db_payment_status = payment_status_map.get(status, "PENDING")
        merchant_confirmed = 1 if state.get("merchant_response") == "Y" else 0

        # 1. Insert/Update Orders Table safely without destructive overwrite of payment_id or PAID status
        cursor.execute(
            """
            INSERT INTO orders (
                id, negotiation_id, product_id, merchant_id, buyer_id, 
                quantity, amount, payment_status, settlement_status, 
                payment_link_id, payment_link_url, merchant_confirmed, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_SETTLEMENT', ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                payment_link_id = COALESCE(excluded.payment_link_id, orders.payment_link_id),
                payment_link_url = COALESCE(excluded.payment_link_url, orders.payment_link_url),
                merchant_confirmed = excluded.merchant_confirmed,
                updated_at = CURRENT_TIMESTAMP
            WHERE orders.payment_status NOT IN ('PAID', 'SETTLED')
            """,
            (
                order_id,
                state.get("negotiation_id"),
                state.get("product_id"),
                state.get("merchant_id"),
                state.get("buyer_id", "b1"),
                state.get("quantity", 1),
                state.get("agreed_price", 0),
                db_payment_status,
                state.get("payment_link_id"),
                state.get("payment_link_url"),
                merchant_confirmed,
                state.get("expires_at")
            )
        )

        # 2. Maintain stock_reservations table invariant (only if not already created)
        if db_payment_status == "PENDING_PAYMENT":
            res_id = f"res_{uuid.uuid4().hex[:10]}"
            expires_at = state.get("expires_at") or (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(
                """
                INSERT INTO stock_reservations (
                    id, order_id, product_id, quantity, status, expires_at
                ) VALUES (?, ?, ?, ?, 'ACTIVE', ?)
                ON CONFLICT(order_id) DO NOTHING
                """,
                (res_id, order_id, state.get("product_id"), state.get("quantity", 1), expires_at)
            )

        # 3. Insert into Audit Log
        audit_action = f"TRUST_{status}"
        cursor.execute(
            "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
            (audit_action, "TrustAgent", state.get("audit_reasoning", f"Trust agent processed order {order_id}."))
        )

        conn.commit()
    except Exception as e:
        print(f"⚠️ Trust DB Persist error: {e}")
    finally:
        conn.close()

    return {}


# ==========================================
# 2. CONDITIONAL ROUTING & GRAPH COMPILATION
# ==========================================

def _route_after_guardrails(state: TrustAgentState) -> str:
    """Routes to merchant confirmation if guardrails passed, otherwise directly to failure."""
    if state.get("guardrail_status") != "PASSED":
        return "handle_failure"
    return "merchant_confirmation"


def _route_after_merchant(state: TrustAgentState) -> str:
    """Routes to payment generation if merchant confirmed ('Y'), else failure/alternatives."""
    if state.get("merchant_response") == "Y":
        return "generate_payment_link"
    return "handle_failure"


# Construct LangGraph StateGraph
workflow = StateGraph(TrustAgentState)

workflow.add_node("init_and_verify_guardrails", init_and_verify_guardrails_node)
workflow.add_node("merchant_confirmation", merchant_confirmation_node)
workflow.add_node("generate_payment_link", generate_payment_link_node)
workflow.add_node("handle_failure", handle_failure_node)
workflow.add_node("persist_order_and_audit", persist_order_and_audit_node)

workflow.add_edge(START, "init_and_verify_guardrails")

workflow.add_conditional_edges("init_and_verify_guardrails", _route_after_guardrails, {
    "merchant_confirmation": "merchant_confirmation",
    "handle_failure": "handle_failure"
})

workflow.add_conditional_edges("merchant_confirmation", _route_after_merchant, {
    "generate_payment_link": "generate_payment_link",
    "handle_failure": "handle_failure"
})

workflow.add_edge("generate_payment_link", "persist_order_and_audit")
workflow.add_edge("handle_failure", "persist_order_and_audit")
workflow.add_edge("persist_order_and_audit", END)

trust_graph = workflow.compile()


# ==========================================
# 3. PUBLIC ENTRYPOINT
# ==========================================

def run_trust_agent(
    product_id: str,
    agreed_price: int,
    quantity: int = 1,
    merchant_response: str | None = None,
    negotiation_id: str | None = None,
    buyer_id: str = "b1",
    buyer_phone: str = "9876543210",
    buyer_name: str = "Ananya Sharma",
    buyer_max_budget: int | None = None,
    order_id: str | None = None
) -> dict[str, Any]:
    """
    Public entrypoint to run the Trust & Safety Agent via LangGraph.
    """
    active_order_id = order_id or f"ord_{uuid.uuid4().hex[:10]}"

    initial_state: TrustAgentState = {
        "order_id": active_order_id,
        "negotiation_id": negotiation_id,
        "product_id": product_id,
        "merchant_id": "",
        "buyer_id": buyer_id,
        "buyer_phone": buyer_phone,
        "buyer_name": buyer_name,
        "agreed_price": agreed_price,
        "quantity": quantity,
        "buyer_max_budget": buyer_max_budget,
        "merchant_response": merchant_response,
        "product": None,
        "merchant": None,
        "buyer_trust": None,
        "guardrail_status": "PENDING",
        "guardrail_reason": "",
        "payment_link_id": None,
        "payment_link_url": None,
        "expires_at": None,
        "alternatives": [],
        "status": "INITIATED",
        "message": "",
        "audit_reasoning": ""
    }

    final_state = trust_graph.invoke(initial_state)

    return {
        "order_id": final_state["order_id"],
        "status": final_state["status"],
        "guardrail_status": final_state.get("guardrail_status"),
        "merchant_response": final_state.get("merchant_response"),
        "product_id": final_state["product_id"],
        "product_name": (final_state.get("product") or {}).get("product_name", "Product"),
        "merchant_name": (final_state.get("merchant") or {}).get("name", "Merchant"),
        "amount": final_state.get("agreed_price"),
        "quantity": final_state.get("quantity", 1),
        "payment_link_id": final_state.get("payment_link_id"),
        "payment_link_url": final_state.get("payment_link_url"),
        "expires_at": final_state.get("expires_at"),
        "is_simulated": not razorpay_client.is_live,
        "alternatives": final_state.get("alternatives", []),
        "message": final_state.get("message", ""),
        "audit_reasoning": final_state.get("audit_reasoning", ""),
        "buyer_trust": final_state.get("buyer_trust"),
        **generate_execution_provenance(
            payment_mode="live" if razorpay_client.is_live else "simulation"
        )
    }
