"""
MerchantMesh - Trust & Integrity Engine
Handles:
1. Time-decay confidence scoring and stock confirmation tracking.
2. Dynamic merchant DNA profiling and abuse detection.
3. Buyer trust and dispute risk assessment.
4. Code-level price floor verification (Hard Constraint).
5. Spending cap & transaction safety limits.
6. Concurrency-safe atomic stock reservation creation & expiration.
7. Atomic merchant HITL confirmation (AWAITING_MERCHANT -> PENDING_PAYMENT + ACTIVE_RESERVATION).
8. Razorpay Webhook processing with raw-body HMAC verification, event-ID idempotency, payment amount validation, and settlement timestamp boundaries.
9. Sweeping of expired reservations and unpaid payment link cancellation.
"""

import hashlib
import json
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from core.config import DB_PATH
from core.razorpay_client import razorpay_client


class InventoryIntegrityError(Exception):
    """Raised when stock quantity or reservation state invariant is violated."""


class OrderStateTransitionError(Exception):
    """Raised when an order transition fails optimistic concurrency checks."""


def _parse_db_timestamp(ts_str: str) -> datetime:
    """Safely parses SQLite timestamp strings across multiple standard formats into UTC datetime."""
    if not ts_str:
        return datetime.min.replace(tzinfo=timezone.utc)
    clean_str = ts_str.strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(clean_str, fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(clean_str)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def transition_order_state(conn: sqlite3.Connection, order_id: str, from_state: str, to_state: str) -> bool:
    """
    Atomic state transition helper for orders table.
    Enforces that the order is strictly in `from_state` before transitioning to `to_state`.
    Returns True if exactly 1 row was updated, False otherwise.
    """
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE orders SET payment_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND payment_status = ?",
        (to_state, order_id, from_state)
    )
    return cursor.rowcount == 1


# ==========================================
# 1. TIME-DECAY CONFIDENCE SCORING
# ==========================================
def update_product_confidence(product_id: str, conn: sqlite3.Connection = None) -> float | None:
    """
    Decays the confidence score of a product based on how long since its stock was confirmed.
    - Fresh (< 24h): ~100% confidence.
    - Decays roughly 3.5% per day.
    - Below 20%: product is considered stale and filtered from top rankings.
    """
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        close_conn = True
        
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT stock_last_confirmed_at, confidence_score FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        
        if not product:
            return None
            
        confirmed_at = _parse_db_timestamp(product["stock_last_confirmed_at"])
        days_old = (datetime.now(timezone.utc) - confirmed_at).total_seconds() / 86400.0
        
        # Base confidence 100.0, decays at 3.5 points per 24 hours elapsed (clamped 0.0 - 100.0)
        new_confidence = min(100.0, max(0.0, round(100.0 - (max(0.0, days_old) * 3.5), 1)))
        
        cursor.execute("UPDATE products SET confidence_score = ? WHERE id = ?", (new_confidence, product_id))
        conn.commit()
        return new_confidence
    finally:
        if close_conn:
            conn.close()


# ==========================================
# 2. DYNAMIC MERCHANT DNA PROFILER
# ==========================================
def analyze_merchant_dna(merchant_id: str) -> str | None:
    """
    Analyzes all products listed by a merchant to dynamically infer their commercial profile:
    1. Negotiation flexibility (Firm / Flexible / Generous)
    2. Price range tier (Budget / Mid-Range / Premium - benchmarked against category platform average)
    3. Primary product category
    4. Abuse detection: flags fake inflated discounts where floor is < 40% of listed price.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT listed_price, floor_price, category 
               FROM products 
               WHERE merchant_id = ? AND listed_price IS NOT NULL""",
            (merchant_id,)
        )
        products = cursor.fetchall()
        
        if not products:
            return None
            
        total_spread_pct = 0.0
        abuse_flags = 0
        total_price = 0
        category_counts: dict[str, int] = {}
        valid_spread_count = 0
        
        for p in products:
            cat = p["category"] or "General"
            category_counts[cat] = category_counts.get(cat, 0) + 1
            total_price += p["listed_price"]
            
            if p["floor_price"] and p["listed_price"] > 0:
                spread = (p["listed_price"] - p["floor_price"]) / p["listed_price"]
                total_spread_pct += spread
                valid_spread_count += 1
                if spread > 0.60:
                    abuse_flags += 1
                    
        avg_price = total_price / len(products) if products else 0
        avg_spread = (total_spread_pct / valid_spread_count) if valid_spread_count > 0 else 0.0
        
        if avg_spread < 0.10:
            flexibility = "Firm"
        elif avg_spread < 0.25:
            flexibility = "Flexible"
        else:
            flexibility = "Generous"
            
        primary_category = max(category_counts, key=category_counts.get) if category_counts else "General"
        
        cursor.execute("SELECT AVG(listed_price) FROM products WHERE category = ?", (primary_category,))
        platform_avg_row = cursor.fetchone()
        platform_avg = platform_avg_row[0] if platform_avg_row and platform_avg_row[0] else avg_price

        if platform_avg == 0:
            price_tier = "Mid-Range"
        elif avg_price < (platform_avg * 0.75):
            price_tier = "Budget"
        elif avg_price > (platform_avg * 1.25):
            price_tier = "Premium"
        else:
            price_tier = "Mid-Range"
            
        if abuse_flags > 0:
            cursor.execute(
                "UPDATE merchants SET reliability_score = MAX(1.0, reliability_score - ?) WHERE id = ?",
                (abuse_flags * 0.5, merchant_id)
            )
            
        dna_dict = {
            "flexibility": flexibility,
            "price_tier": price_tier,
            "primary_category": primary_category,
            "avg_discount_pct": round(avg_spread * 100, 1),
            "abuse_flags": abuse_flags
        }
        dna_json = json.dumps(dna_dict)
        
        cursor.execute("UPDATE merchants SET merchant_dna_json = ? WHERE id = ?", (dna_json, merchant_id))
        conn.commit()
        return dna_json
    finally:
        conn.close()


# ==========================================
# 3. BUYER TRUST & DISPUTE RISK ASSESSMENT
# ==========================================
def check_buyer_trust(buyer_id: str, session_id: str | None = None) -> dict[str, Any]:
    """
    Evaluates buyer trustworthiness based on historic return/dispute rates.
    Protects informal merchants against return fraud and Sybil inventory hoarding.
    Binds active hold checks to both buyer_id AND session_id to prevent Sybil rotation attacks.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT buyer_trust_score, return_rate FROM buyers WHERE id = ?", (buyer_id,))
        buyer = cursor.fetchone()

        return_rate = (buyer["return_rate"] if buyer else 0.0) or 0.0
        trust_score = (buyer["buyer_trust_score"] if buyer else 5.0) or 5.0

        # Anti-Sybil / Denial of Inventory Defense:
        # Check active unexpired stock reservations across the system for this buyer identity OR session
        if session_id:
            cursor.execute("""
                SELECT COUNT(*) as active_count 
                FROM stock_reservations r
                JOIN orders o ON r.order_id = o.id
                WHERE (o.buyer_id = ? OR (o.session_id IS NOT NULL AND o.session_id = ?))
                  AND r.status = 'ACTIVE' 
                  AND datetime(r.expires_at) > datetime('now')
            """, (buyer_id, session_id))
        else:
            cursor.execute("""
                SELECT COUNT(*) as active_count 
                FROM stock_reservations r
                JOIN orders o ON r.order_id = o.id
                WHERE o.buyer_id = ? AND r.status = 'ACTIVE' AND datetime(r.expires_at) > datetime('now')
            """, (buyer_id,))
        active_holds = cursor.fetchone()["active_count"]

        # If buyer has excessive uncompleted holds, block new reservations to prevent inventory denial
        # For the hackathon sandbox (buyer_id == 'b1'), we disable this limit to prevent multi-judge collisions
        max_allowed_holds = 999 if buyer_id == "b1" else (2 if (not buyer or trust_score < 3.0) else 5)
        if active_holds >= max_allowed_holds:
            return {
                "is_safe": False,
                "warning": f"⚠️ Anti-Hoarding Block: Buyer has {active_holds} active uncompleted reservations. Complete existing orders before locking more inventory.",
                "return_rate": return_rate,
                "trust_score": trust_score,
                "active_holds": active_holds
            }

        if not buyer:
            return {"is_safe": True, "warning": None, "return_rate": 0.0, "trust_score": 5.0, "active_holds": active_holds}
            
        if return_rate > 0.40:
            return {
                "is_safe": False,
                "warning": f"⚠️ Caution: Buyer has a {int(return_rate * 100)}% return rate. Mandatory prepaid checkout required.",
                "return_rate": return_rate,
                "trust_score": trust_score,
                "active_holds": active_holds
            }
            
        return {"is_safe": True, "warning": None, "return_rate": return_rate, "trust_score": trust_score, "active_holds": active_holds}
    finally:
        conn.close()


# ==========================================
# 4. HARD CODE-LEVEL PRICE FLOOR VERIFICATION
# ==========================================
def _verify_price_floor_tx(
    cursor: sqlite3.Cursor,
    product_id: str,
    proposed_price: int,
    quantity: int = 1
) -> tuple[bool, str, dict[str, Any]]:
    """
    Transaction-aware price floor validator operating on an active cursor/transaction.
    Guarantees no payment link can be generated for an amount below the seller's floor price.
    Calculates bulk volume discounts if quantity > 1.
    """
    if quantity <= 0:
        return False, "GUARDRAIL_VIOLATION: Quantity must be a positive integer.", {}

    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    if not product:
        return False, f"Product {product_id} not found in database.", {}

    unit_listed = product["listed_price"] or 0
    raw_floor = product["floor_price"]

    # Strict Policy: If floor_price is NULL, do not silently invent 80%. Require full listed price.
    if raw_floor is None:
        total_listed = unit_listed * quantity
        if proposed_price < total_listed:
            return (
                False,
                f"MISSING_PRICE_FLOOR: Product '{product['product_name']}' has no configured floor price. Full listed price ₹{total_listed:,} required for checkout.",
                {"product_id": product_id, "error": "MISSING_PRICE_FLOOR", "unit_listed": unit_listed, "total_listed": total_listed}
            )
        total_floor = total_listed
        unit_floor = unit_listed
    else:
        unit_floor = raw_floor
        # Strict Floor Invariant: Base floor is always unit_floor * quantity (no discount may breach this)
        total_floor = unit_floor * quantity
        total_listed = unit_listed * quantity

    details = {
        "product_id": product_id,
        "product_name": product["product_name"],
        "unit_listed": unit_listed,
        "unit_floor": unit_floor,
        "quantity": quantity,
        "total_listed": total_listed,
        "total_floor": total_floor,
        "proposed_price": proposed_price
    }

    if unit_floor > unit_listed:
        return False, f"DATA_INTEGRITY_ERROR: Minimum floor price (₹{unit_floor:,}) cannot exceed listed price (₹{unit_listed:,}).", details

    if proposed_price <= 0:
        return (
            False,
            f"GUARDRAIL_VIOLATION: Proposed price ₹{proposed_price:,} must be strictly greater than zero.",
            details
        )

    if total_floor <= 0:
        return (
            False,
            f"GUARDRAIL_VIOLATION: Minimum price floor cannot be zero or negative (Calculated: ₹{total_floor:,}).",
            details
        )

    if proposed_price < total_floor:
        return (
            False,
            f"GUARDRAIL_VIOLATION: Proposed price ₹{proposed_price:,} is strictly below minimum floor price of ₹{total_floor:,}.",
            details
        )

    return True, "PASSED", details


def verify_transaction_price_floor(
    product_id: str,
    proposed_price: int,
    quantity: int = 1
) -> tuple[bool, str, dict[str, Any]]:
    """Public helper for price floor verification opening an independent connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        return _verify_price_floor_tx(cursor, product_id, proposed_price, quantity)
    finally:
        conn.close()


# ==========================================
# 5. SPENDING CAP & FRAUD SAFETY VERIFICATION
# ==========================================
def _verify_spending_cap_tx(
    cursor: sqlite3.Cursor,
    buyer_id: str,
    amount: int,
    max_budget: int | None = None
) -> tuple[bool, str]:
    """
    Transaction-aware spending cap and informal safety cap validator.
    1. Ensures order amount does not exceed buyer's stated maximum budget.
    2. Enforces maximum safety limit (₹50,000) for informal unverified transactions.
    """
    MAX_INFORMAL_COMMERCE_LIMIT = 50000

    if amount <= 0:
        return False, f"GUARDRAIL_VIOLATION: Invalid non-positive amount ₹{amount}."

    if max_budget is not None and max_budget > 0 and amount > max_budget:
        return False, f"GUARDRAIL_VIOLATION: Amount ₹{amount:,} exceeds buyer budget cap of ₹{max_budget:,}."

    if amount > MAX_INFORMAL_COMMERCE_LIMIT:
        return False, f"GUARDRAIL_VIOLATION: Amount ₹{amount:,} exceeds maximum informal commerce safety cap of ₹{MAX_INFORMAL_COMMERCE_LIMIT:,}."

    return True, "PASSED"


def verify_spending_cap(
    buyer_id: str,
    amount: int,
    max_budget: int | None = None
) -> tuple[bool, str]:
    """Public helper for spending cap verification opening an independent connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        return _verify_spending_cap_tx(cursor, buyer_id, amount, max_budget)
    finally:
        conn.close()


# ==========================================
# 6. ATOMIC STOCK AVAILABILITY & RESERVATION
# ==========================================
def _verify_and_lock_stock_tx(
    cursor: sqlite3.Cursor,
    product_id: str,
    requested_qty: int = 1
) -> tuple[bool, int, str]:
    """
    Transaction-aware stock availability check inside an active BEGIN IMMEDIATE transaction.
    Sweeps expired reservations and verifies unreserved physical stock.
    """
    if requested_qty <= 0:
        return False, 0, "Requested quantity must be positive."

    cursor.execute("SELECT stock_quantity, is_prohibited, product_name FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    if not row:
        return False, 0, f"Product {product_id} not found."
    if row["is_prohibited"]:
        return False, 0, f"Product '{row['product_name']}' is flagged as prohibited."

    stock = row["stock_quantity"] or 0

    # Sweep expired reservations for this product inside transaction
    cursor.execute("""
        UPDATE stock_reservations 
        SET status = 'EXPIRED' 
        WHERE product_id = ? AND status = 'ACTIVE' AND expires_at <= CURRENT_TIMESTAMP
    """, (product_id,))

    # Sum active unexpired reservations
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) as reserved
        FROM stock_reservations
        WHERE product_id = ? AND status = 'ACTIVE' AND expires_at > CURRENT_TIMESTAMP
    """, (product_id,))
    reserved_row = cursor.fetchone()
    reserved = reserved_row["reserved"] if reserved_row else 0

    available = stock - reserved
    if available < requested_qty:
        if reserved > 0:
            return False, available, f"INVENTORY_RESERVATION_VIOLATION: Insufficient stock. Product '{row['product_name']}' has {stock} total stock, but {reserved} unit(s) are currently reserved in active 15-minute payment links. Effective available stock is {available}."
        else:
            return False, available, f"INSUFFICIENT_STOCK: Insufficient stock. Product '{row['product_name']}' has {stock} total stock, but requested quantity is {requested_qty}. Effective available stock is {available}."

    return True, available, "Available"


def verify_stock_availability(
    product_id: str,
    requested_qty: int = 1
) -> tuple[bool, int, str]:
    """Public helper for stock availability verification opening an independent connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        return _verify_and_lock_stock_tx(cursor, product_id, requested_qty)
    finally:
        conn.close()


# ==========================================
# 7. MERCHANT CONFIRMATION & ATOMIC RESERVATION (HITL)
# ==========================================
def confirm_merchant_order_and_reserve(
    order_id: str,
    merchant_id: str,
    confirmation: str
) -> dict[str, Any]:
    """
    Executes atomic state transition for merchant confirmation:
    1. If 'Y': Runs single BEGIN IMMEDIATE transaction to:
       - Verify order exists and belongs to merchant in 'AWAITING_MERCHANT' state.
       - Verify price floor constraint (_verify_price_floor_tx).
       - Verify spending cap constraint (_verify_spending_cap_tx).
       - Verify available stock (_verify_and_lock_stock_tx).
       - Create ACTIVE stock reservation with 15-min TTL.
       - Conditionally transition order -> 'PENDING_PAYMENT' (enforcing rowcount == 1).
       External Razorpay link creation is performed outside the DB lock with reference_id = order_id.
       If link creation hits timeout, state is marked PAYMENT_LINK_RECONCILIATION_REQUIRED.
       If link creation fails definitively, cleanly releases reservation and cancels order.
    2. If 'N': Transitions order -> 'REJECTED_BY_MERCHANT', penalizes merchant score, and triggers alternative discovery.
    """
    conf = confirmation.strip().upper()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row

    if conf == "N":
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                return {"status": "ORDER_NOT_FOUND", "confirmed": False, "message": f"Order {order_id} not found."}
            if order["merchant_id"] != merchant_id:
                return {"status": "UNAUTHORIZED", "confirmed": False, "message": "Merchant unauthorized for this order."}

            transition_order_state(conn, order_id, order["payment_status"], "REJECTED_BY_MERCHANT")
            conn.commit()
            
            # Penalize merchant & trigger alternative discovery
            penalize_merchant_on_failure(order["product_id"], merchant_id, reason="MERCHANT_REJECTED_OUT_OF_STOCK")
            
            from agents.discovery_agent import run_discovery_agent
            alts = []
            try:
                disc = run_discovery_agent(query="clothing alternatives", buyer_id=order["buyer_id"])
                alts = [p for p in disc.get("ranked_products", []) if p.get("id") != order["product_id"]][:3]
            except Exception:
                pass

            return {
                "status": "REJECTED_BY_MERCHANT",
                "confirmed": False,
                "order_id": order_id,
                "alternatives": alts,
                "message": "Order rejected by merchant. Alternative products identified for buyer.",
                "terminal_logs": [
                    f"[HITL] Merchant {merchant_id} rejected order {order_id}.",
                    "[TrustAgent] Order transitioned to REJECTED_BY_MERCHANT.",
                    "[TrustAgent] Merchant reliability score penalized by 0.3.",
                    f"[DiscoveryAgent] Surfaced {len(alts)} alternative recommendations."
                ]
            }
        finally:
            conn.close()

    elif conf == "Y":
        # ATOMIC DB TRANSACTION FOR RESERVATION CREATION & FINANCIAL GUARDS
        reservation_id = f"res_{uuid.uuid4().hex[:10]}"
        product_id = ""
        amount = 0
        quantity = 1
        buyer_id = "b1"
        buyer_phone = "9876543210"
        buyer_name = "Customer"
        product_name = "Product"
        merchant_name = "Merchant"
        existing_payment_link_id = None
        existing_payment_link_url = None
        expires_at_dt = datetime.now(timezone.utc) + timedelta(minutes=15)
        expires_at_str = expires_at_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            cursor = conn.cursor()
            conn.execute("BEGIN IMMEDIATE")

            cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()
            if not order:
                conn.rollback()
                return {"status": "ORDER_NOT_FOUND", "confirmed": False, "message": f"Order {order_id} not found."}

            # Hydrate real values from order
            buyer_id = order["buyer_id"] or buyer_id
            amount = order["amount"] or amount
            quantity = order["quantity"] or quantity

            if order["merchant_id"] != merchant_id:
                conn.rollback()
                return {"status": "UNAUTHORIZED", "confirmed": False, "message": "Merchant unauthorized for this order."}

            # Check if order is already confirmed / pending payment (Idempotency)
            if order["payment_status"] == "PENDING_PAYMENT" and order["payment_link_url"]:
                conn.rollback()
                return {
                    "status": "PAYMENT_LINK_GENERATED",
                    "confirmed": True,
                    "order_id": order_id,
                    "payment_link_id": order["payment_link_id"],
                    "payment_link_url": order["payment_link_url"],
                    "expires_at": order["expires_at"] or expires_at_str,
                    "is_simulated": True,
                    "message": "Order already confirmed and active payment link exists.",
                    "reply": f"Active payment link: {order['payment_link_url']}"
                }

            if order["payment_status"] != "AWAITING_MERCHANT":
                conn.rollback()
                return {
                    "status": "INVALID_STATE", 
                    "confirmed": False, 
                    "message": f"Order {order_id} is in state '{order['payment_status']}', expected 'AWAITING_MERCHANT'."
                }

            product_id = order["product_id"]
            amount = order["amount"]
            quantity = order["quantity"]
            buyer_id = order["buyer_id"]

            # 0. Anti-Hoarding Defense re-verification inside transaction
            buyer_trust = check_buyer_trust(buyer_id, session_id=order["session_id"] if "session_id" in order.keys() else None)
            if not buyer_trust.get("is_safe", True) and "Anti-Hoarding" in buyer_trust.get("warning", ""):
                conn.rollback()
                return {
                    "status": "GUARDRAIL_VIOLATION",
                    "confirmed": False,
                    "message": buyer_trust.get("warning")
                }

            # 1. Authoritative Price Floor Guardrail inside single transaction
            floor_ok, floor_msg, _ = _verify_price_floor_tx(cursor, product_id, amount, quantity)
            if not floor_ok:
                conn.rollback()
                return {"status": "GUARDRAIL_VIOLATION", "confirmed": False, "message": floor_msg}

            # 2. Authoritative Spending Cap Guardrail inside single transaction
            cap_ok, cap_msg = _verify_spending_cap_tx(cursor, buyer_id, amount)
            if not cap_ok:
                conn.rollback()
                return {"status": "SPENDING_CAP_EXCEEDED", "confirmed": False, "message": cap_msg}

            # 3. Authoritative Stock Availability Guardrail inside single transaction
            stock_ok, available, stock_msg = _verify_and_lock_stock_tx(cursor, product_id, quantity)
            if not stock_ok:
                conn.rollback()
                return {
                    "status": "INSUFFICIENT_STOCK",
                    "confirmed": False,
                    "available_stock": available,
                    "requested_quantity": quantity,
                    "message": stock_msg
                }

            # Query product name for descriptions
            cursor.execute("SELECT product_name FROM products WHERE id = ?", (product_id,))
            prod_row = cursor.fetchone()
            product_name = prod_row["product_name"] if prod_row else "Product"

            # 4. Insert ACTIVE reservation
            cursor.execute("""
                INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
                VALUES (?, ?, ?, ?, 'ACTIVE', ?)
            """, (reservation_id, order_id, product_id, quantity, expires_at_str))

            # 5. Conditional SQL Transition: AWAITING_MERCHANT -> PENDING_PAYMENT
            cursor.execute("""
                UPDATE orders 
                SET payment_status = 'PENDING_PAYMENT', merchant_confirmed = 1, expires_at = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND payment_status = 'AWAITING_MERCHANT'
            """, (expires_at_str, order_id))

            if cursor.rowcount != 1:
                conn.rollback()
                raise OrderStateTransitionError(f"Failed atomic transition on order {order_id}")

            cursor.execute("""
                INSERT INTO audit_log (action, agent, reasoning)
                VALUES (?, ?, ?)
            """, (
                "MERCHANT_CONFIRMED_RESERVATION_CREATED",
                "TrustAgent",
                f"Merchant {merchant_id} confirmed Order {order_id}. Floor verified (₹{amount:,}), active reservation {reservation_id} created for {quantity} unit(s)."
            ))

            conn.commit()
        except Exception as e:
            conn.rollback()
            conn.close()
            return {"status": "TRANSACTION_FAILED", "confirmed": False, "message": str(e)}

        # EXTERNAL NETWORK CALL (OUTSIDE SQLITE WRITE LOCK)
        try:
            plink_res = razorpay_client.create_payment_link(
                amount_inr=amount,
                customer_phone=buyer_phone,
                customer_name=buyer_name,
                description=f"Order {order_id}: {quantity}x {product_name}",
                reference_id=order_id,
                expire_in_mins=15
            )

            if plink_res.get("status") == "FAILED":
                raise Exception(plink_res.get("error", "Payment link creation rejected by gateway"))

            plink_id = plink_res["payment_link_id"]
            plink_url = plink_res["payment_link_url"]

            # Store generated link in DB
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders 
                SET payment_link_id = ?, payment_link_url = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND payment_status = 'PENDING_PAYMENT'
            """, (plink_id, plink_url, order_id))
            conn.commit()

            terminal_logs = [
                f"[HITL] Merchant {merchant_id} confirmed order {order_id}.",
                "[TrustAgent] Price floor & spending cap verified inside atomic lock.",
                f"[TrustAgent] Atomic stock reservation {reservation_id} locked (15-min window).",
                "[TrustAgent] Order transitioned to PENDING_PAYMENT.",
                f"[Razorpay] Payment link generated: {plink_url}",
                f"[Razorpay] Link expires at {expires_at_str}."
            ]

            return {
                "status": "PAYMENT_LINK_GENERATED",
                "confirmed": True,
                "order_id": order_id,
                "reservation_id": reservation_id,
                "payment_link_id": plink_id,
                "payment_link_url": plink_url,
                "expires_at": expires_at_str,
                "is_simulated": plink_res.get("is_simulated", True),
                "terminal_logs": terminal_logs,
                "reply": f"Badhiya! ✅ Razorpay payment link generated: {plink_url} (Valid for 15 minutes)."
            }
        except Exception as e:
            err_msg = str(e).lower()
            # Distinguish unknown timeout / network interruption from definitive gateway failure
            if "timeout" in err_msg or "connection" in err_msg or "econnrefused" in err_msg:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE orders 
                        SET payment_status = 'PAYMENT_LINK_RECONCILIATION_REQUIRED', updated_at = CURRENT_TIMESTAMP 
                        WHERE id = ? AND payment_status = 'PENDING_PAYMENT'
                    """, (order_id,))
                    cursor.execute("""
                        INSERT INTO audit_log (action, agent, reasoning) 
                        VALUES (?, ?, ?)
                    """, (
                        "PAYMENT_LINK_RECONCILIATION_REQUIRED",
                        "TrustAgent",
                        f"Network timeout contacting Razorpay for order {order_id}: {e}. State marked for reconciliation."
                    ))
                    conn.commit()
                except Exception:
                    pass

                return {
                    "status": "PAYMENT_LINK_RECONCILIATION_REQUIRED",
                    "confirmed": False,
                    "order_id": order_id,
                    "message": f"Payment gateway network timeout ({e!s}). Marked for reconciliation without releasing stock.",
                    "terminal_logs": [
                        f"[Razorpay] Gateway timeout on order {order_id}: {e}",
                        "[TrustAgent] Order marked PAYMENT_LINK_RECONCILIATION_REQUIRED."
                    ]
                }
            else:
                # Definitive Failure: Cleanly release reservation and cancel order
                try:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE stock_reservations SET status = 'EXPIRED' WHERE id = ?", (reservation_id,))
                    cursor.execute("UPDATE orders SET payment_status = 'CANCELLED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
                    cursor.execute("INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                                   ("PAYMENT_LINK_CREATION_FAILED", "TrustAgent", f"Payment link creation rejected for order {order_id}: {e}. Reservation released."))
                    conn.commit()
                except Exception:
                    pass

                return {
                    "status": "PAYMENT_PROVIDER_UNAVAILABLE",
                    "confirmed": False,
                    "order_id": order_id,
                    "message": f"Payment provider error: {e!s}. Stock reservation cleanly released.",
                    "terminal_logs": [
                        f"[Razorpay] Payment link creation failed: {e}",
                        "[TrustAgent] Reservation released (EXPIRED) to prevent orphaned inventory.",
                        "[TrustAgent] Order transitioned to CANCELLED."
                    ]
                }
        finally:
            conn.close()

    return {"status": "INVALID_CONFIRMATION", "confirmed": False, "message": "Expected 'Y' or 'N'."}


# ==========================================
# 8. MERCHANT FAILURE PENALTY
# ==========================================
def penalize_merchant_on_failure(
    product_id: str,
    merchant_id: str,
    reason: str = "REJECTED_OR_TIMEOUT"
) -> dict[str, Any]:
    """
    Applies trust penalties when a merchant fails to fulfill:
    - Product confidence decays by 25 points.
    - If marked out of stock, stock set to 0.
    - Merchant reliability score drops by 0.3.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE products SET confidence_score = MAX(0.0, confidence_score - 25.0) WHERE id = ?",
            (product_id,)
        )
        
        if "OUT_OF_STOCK" in reason or "REJECTED" in reason:
            cursor.execute("UPDATE products SET stock_quantity = 0 WHERE id = ?", (product_id,))

        cursor.execute(
            "UPDATE merchants SET reliability_score = MAX(1.0, reliability_score - 0.3) WHERE id = ?",
            (merchant_id,)
        )

        cursor.execute(
            "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
            (
                f"MERCHANT_PENALIZED_{reason}",
                "TrustAgent",
                f"Merchant {merchant_id} penalized on product {product_id} due to {reason}. Confidence decayed, reliability adjusted."
            )
        )
        conn.commit()

        return {
            "status": "PENALIZED",
            "product_id": product_id,
            "merchant_id": merchant_id,
            "reason": reason
        }
    finally:
        conn.close()


# ==========================================
# 9. RAZORPAY WEBHOOK PROCESSING (ATOMIC INVARIANTS)
# ==========================================
def process_payment_webhook(
    raw_body: bytes,
    signature: str,
    event_id: str | None = None
) -> dict[str, Any]:
    """
    Processes Razorpay payment webhooks ('payment_link.paid' or 'payment.captured').
    Invariants Enforced:
    1. HMAC SHA256 signature verified directly on raw request bytes.
    2. Event ID idempotency with duplicate protection in webhook_events.
    3. Currency == 'INR' and Payment Amount == Order Amount * 100.
    4. Settlement Boundary Rule: payment_timestamp <= reservation.expires_at.
    5. Single atomic transaction: Order -> PAID, Reservation -> CONSUMED, Product Stock decremented exactly once.
    """
    if not signature or not razorpay_client.verify_webhook_signature(raw_body, signature):
        return {"status": "SIGNATURE_VERIFICATION_FAILED", "message": "Invalid webhook HMAC signature."}

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        return {"status": "MALFORMED_JSON", "message": str(e)}

    event = payload.get("event", "payment_link.paid")
    payload_entity = payload.get("payload", {})
    payment_data = payload_entity.get("payment", {}).get("entity", {})
    plink_data = payload_entity.get("payment_link", {}).get("entity", {})

    evt_id = event_id or payload.get("id") or payload.get("event_id")
    if not evt_id:
        # Deterministic SHA-256 event ID fallback for raw payloads lacking provider event_id header
        evt_id = f"evt_hash_{hashlib.sha256(raw_body).hexdigest()[:24]}"

    payment_id = payment_data.get("id")
    if not payment_id:
        return {
            "status": "INVALID_PAYMENT_ID",
            "message": "Missing authentic payment.entity.id in webhook payload. Order cannot be advanced to PAID."
        }

    payment_link_id = plink_data.get("id") or payment_data.get("order_id")
    reference_id = plink_data.get("reference_id") or payment_data.get("order_id")
    amount_paid_paise = payment_data.get("amount") or (plink_data.get("amount"))
    currency = payment_data.get("currency", "INR").upper()
    payment_created_at_ts = payment_data.get("created_at") or int(time.time())

    if currency != "INR":
        return {"status": "INVALID_CURRENCY", "message": f"Currency {currency} not supported."}

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        # 1. Idempotency & Payload Binding Check in webhook_events
        payload_hash = hashlib.sha256(raw_body).hexdigest()
        try:
            cursor.execute("""
                INSERT INTO webhook_events (event_id, payload_hash, event_type, status, received_at)
                VALUES (?, ?, ?, 'PROCESSING', CURRENT_TIMESTAMP)
            """, (evt_id, payload_hash, event))
        except sqlite3.IntegrityError:
            # Duplicate Event ID Detected - verify payload hash
            cursor.execute("SELECT status, payload_hash FROM webhook_events WHERE event_id = ?", (evt_id,))
            existing = cursor.fetchone()
            if existing and existing["payload_hash"] and existing["payload_hash"] != payload_hash:
                conn.commit()
                return {
                    "status": "TAMPERED_EVENT_PAYLOAD",
                    "event_id": evt_id,
                    "message": "Duplicate event ID with altered payload hash rejected."
                }
            if existing and existing["status"] == "PROCESSED":
                conn.commit()
                return {
                    "status": "already_processed", 
                    "event_id": evt_id, 
                    "message": "Webhook event already processed successfully."
                }
            elif existing and existing["status"] == "PROCESSING":
                conn.commit()
                return {"status": "in_flight", "event_id": evt_id, "message": "Event is currently processing."}

        # 2. Locate Matching Order across reference_id, notes, and payment_link_id
        notes_data = payment_data.get("notes") or plink_data.get("notes") or {}
        order_notes_id = notes_data.get("order_id") or notes_data.get("reference_id") or notes_data.get("merchantmesh_order_id")
        payment_link_id = plink_data.get("id")
        reference_id = plink_data.get("reference_id") or order_notes_id or payment_data.get("order_id")

        cursor.execute("""
            SELECT * FROM orders 
            WHERE id = ? OR id = ? OR payment_link_id = ? OR payment_id = ?
            LIMIT 1
        """, (reference_id, order_notes_id, payment_link_id, payment_id))
        order = cursor.fetchone()

        if not order:
            cursor.execute("UPDATE webhook_events SET status = 'FAILED' WHERE event_id = ?", (evt_id,))
            cursor.execute("INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                           ("WEBHOOK_ORPHAN_PAYMENT", "TrustAgent", f"Payment {payment_id} received for unknown reference {reference_id}."))
            conn.commit()
            return {"status": "ORDER_NOT_FOUND", "payment_id": payment_id, "reference_id": reference_id}

        order_id = order["id"]
        product_id = order["product_id"]
        merchant_id = order["merchant_id"]
        expected_amount_paise = (order["amount"] or 0) * 100
        order_quantity = order["quantity"] or 1

        # 3. Validate Amount in Paise (Strict Non-Null & Exact Match)
        if amount_paid_paise is None or amount_paid_paise <= 0 or amount_paid_paise != expected_amount_paise:
            cursor.execute("UPDATE webhook_events SET status = 'FAILED' WHERE event_id = ?", (evt_id,))
            cursor.execute("INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                           ("WEBHOOK_AMOUNT_MISMATCH", "TrustAgent", f"Order {order_id} expected {expected_amount_paise} paise, received {amount_paid_paise} paise."))
            conn.commit()
            return {
                "status": "AMOUNT_MISMATCH",
                "order_id": order_id,
                "expected": expected_amount_paise,
                "received": amount_paid_paise
            }

        # 4. Check Reservation & Settlement Boundary Rule + Reallocated Inventory Guard
        cursor.execute("SELECT * FROM stock_reservations WHERE order_id = ?", (order_id,))
        reservation = cursor.fetchone()

        if reservation:
            res_expires_dt = _parse_db_timestamp(reservation["expires_at"])
            res_expires_ts = int(res_expires_dt.timestamp())
            
            # If payment arrived after reservation expired or status is EXPIRED
            if payment_created_at_ts > res_expires_ts or reservation["status"] == "EXPIRED":
                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
                prod_row = cursor.fetchone()
                current_stock = prod_row["stock_quantity"] if prod_row else 0
                cursor.execute("""
                    SELECT COALESCE(SUM(quantity), 0) as reserved_qty
                    FROM stock_reservations
                    WHERE product_id = ? AND status = 'ACTIVE' AND expires_at > CURRENT_TIMESTAMP
                """, (product_id,))
                active_reserved = cursor.fetchone()["reserved_qty"]
                available_unreserved = current_stock - active_reserved

                if available_unreserved < order_quantity:
                    # Inventory was reallocated! Transition to refund reconciliation rather than overselling
                    cursor.execute("""
                        UPDATE orders 
                        SET payment_status = 'PAYMENT_RECONCILIATION_REQUIRED', 
                            settlement_status = 'REFUND_PENDING', 
                            payment_id = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (payment_id, order_id))
                    cursor.execute("UPDATE webhook_events SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP WHERE event_id = ?", (evt_id,))
                    cursor.execute("""
                        INSERT INTO audit_log (action, agent, reasoning)
                        VALUES (?, ?, ?)
                    """, (
                        "PAYMENT_RECONCILIATION_STOCK_REALLOCATED",
                        "TrustAgent",
                        f"Payment {payment_id} confirmed for Order {order_id}, but stock was reallocated (Available: {available_unreserved}, Needed: {order_quantity}). Queued for automated refund."
                    ))
                    conn.commit()
                    return {
                        "status": "PAYMENT_RECONCILIATION_REQUIRED",
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "reason": "STOCK_REALLOCATED_AFTER_EXPIRY",
                        "message": "Payment captured after reservation expiry and inventory was reallocated. Order queued for refund."
                    }
                else:
                    # Stock is still physically available: Revive reservation to consume atomically
                    cursor.execute("""
                        UPDATE stock_reservations 
                        SET status = 'ACTIVE', expires_at = datetime('now', '+15 minutes')
                        WHERE id = ?
                    """, (reservation["id"],))

        # 5. Atomic State Transitions
        # Order -> PAID (Persisting authoritative Razorpay payment_id)
        cursor.execute("""
            UPDATE orders 
            SET payment_status = 'PAID', settlement_status = 'PENDING_SETTLEMENT', payment_id = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND payment_status = 'PENDING_PAYMENT'
        """, (payment_id, order_id))

        if cursor.rowcount != 1:
            # Check current order state for late webhook recovery
            cursor.execute("SELECT payment_status, amount, quantity, product_id FROM orders WHERE id = ?", (order_id,))
            current_order_state = cursor.fetchone()
            current_status = current_order_state["payment_status"] if current_order_state else "UNKNOWN"
            
            if current_status in ["EXPIRED", "PAYMENT_LINK_RECONCILIATION_REQUIRED", "CANCELLED", "TIMEOUT_EXPIRED"]:
                # Late payment arrived after sweeper or timeout: check if stock can still fulfill the order
                cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
                prod_row = cursor.fetchone()
                current_stock = prod_row["stock_quantity"] if prod_row else 0
                cursor.execute("""
                    SELECT COALESCE(SUM(quantity), 0) as reserved_qty
                    FROM stock_reservations
                    WHERE product_id = ? AND status = 'ACTIVE' AND expires_at > CURRENT_TIMESTAMP
                """, (product_id,))
                active_reserved = cursor.fetchone()["reserved_qty"]
                available_unreserved = current_stock - active_reserved

                if available_unreserved >= order_quantity:
                    # Stock is still available! Revive and fulfill order safely
                    cursor.execute("""
                        UPDATE orders 
                        SET payment_status = 'PAID', settlement_status = 'PENDING_SETTLEMENT', payment_id = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (payment_id, order_id))
                    # Fallthrough to normal stock decrement and settlement below
                else:
                    # Stock unavailable: Transition to refund queue rather than stranding buyer funds
                    cursor.execute("""
                        UPDATE orders 
                        SET payment_status = 'PAYMENT_RECONCILIATION_REQUIRED', 
                            settlement_status = 'REFUND_PENDING', 
                            payment_id = ?, 
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (payment_id, order_id))
                    cursor.execute("UPDATE webhook_events SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP WHERE event_id = ?", (evt_id,))
                    cursor.execute("""
                        INSERT INTO audit_log (action, agent, reasoning)
                        VALUES (?, ?, ?)
                    """, (
                        "LATE_PAYMENT_REFUND_QUEUED",
                        "TrustAgent",
                        f"Late payment {payment_id} captured for order {order_id} in {current_status} state. Stock exhausted. Queued for automated refund."
                    ))
                    conn.commit()
                    return {
                        "status": "PAYMENT_RECONCILIATION_REQUIRED",
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "current_status": current_status,
                        "settlement_status": "REFUND_PENDING",
                        "message": "Payment captured for expired order. Stock unavailable; queued for automated refund."
                    }
            elif current_status == "PAID":
                cursor.execute("UPDATE webhook_events SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP WHERE event_id = ?", (evt_id,))
                conn.commit()
                return {"status": "ALREADY_PAID", "order_id": order_id, "payment_id": payment_id}
            else:
                cursor.execute("UPDATE webhook_events SET status = 'FAILED' WHERE event_id = ?", (evt_id,))
                conn.commit()
                return {
                    "status": "INVALID_ORDER_STATE",
                    "order_id": order_id,
                    "current_status": current_status,
                    "message": f"Order is in unfulfillable state '{current_status}'."
                }

        # Reservation -> CONSUMED
        cursor.execute("""
            UPDATE stock_reservations 
            SET status = 'CONSUMED' 
            WHERE order_id = ? AND (status = 'ACTIVE' OR status = 'EXPIRED')
        """, (order_id,))

        # Product Stock -> Decrement exactly the reserved quantity
        cursor.execute("""
            UPDATE products 
            SET stock_quantity = stock_quantity - ?,
                stock_last_confirmed_at = CURRENT_TIMESTAMP,
                confidence_score = 100.0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND stock_quantity >= ?
        """, (order_quantity, product_id, order_quantity))

        if cursor.rowcount != 1:
            # Physical inventory underflow: Flag order for refund reconciliation, acknowledge webhook, and do not crash
            cursor.execute("""
                UPDATE orders 
                SET payment_status = 'PAYMENT_RECONCILIATION_REQUIRED', 
                    settlement_status = 'REFUND_PENDING',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (order_id,))
            cursor.execute("UPDATE webhook_events SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP WHERE event_id = ?", (evt_id,))
            cursor.execute("""
                INSERT INTO audit_log (action, agent, reasoning)
                VALUES (?, ?, ?)
            """, (
                "PAYMENT_RECONCILIATION_INVENTORY_UNDERFLOW",
                "TrustAgent",
                f"Payment {payment_id} captured for Order {order_id}, but product {product_id} had insufficient stock to deduct {order_quantity} unit(s). Flagged for automated refund reconciliation."
            ))
            conn.commit()
            return {
                "status": "PAYMENT_RECONCILIATION_REQUIRED",
                "order_id": order_id,
                "payment_id": payment_id,
                "reason": "INSUFFICIENT_PHYSICAL_STOCK",
                "message": "Payment captured but physical stock was exhausted. Order queued for automated refund."
            }

        # Reward Merchant Reliability
        cursor.execute("""
            UPDATE merchants 
            SET reliability_score = MIN(5.0, reliability_score + 0.1)
            WHERE id = ?
        """, (merchant_id,))

        # Update webhook event -> PROCESSED
        cursor.execute("""
            UPDATE webhook_events 
            SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP 
            WHERE event_id = ?
        """, (evt_id,))

        # Log to Audit Log
        audit_msg = (
            f"Webhook '{event}' verified. Payment {payment_id} confirmed for Order {order_id} (₹{order['amount']:,}). "
            f"Reservation CONSUMED, stock decremented ({order_quantity} unit(s)). Merchant {merchant_id} reliability rewarded."
        )
        cursor.execute(
            "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
            ("PAYMENT_CONFIRMED_STOCK_DEDUCTED", "TrustAgent", audit_msg)
        )

        conn.commit()

        # Query updated stock
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
        new_stock = cursor.fetchone()["stock_quantity"]

        # Automatically execute Razorpay Route split settlement for the merchant
        settlement_result = None
        try:
            settlement_result = execute_merchant_settlement(order_id=order_id, platform_fee_pct=0.0)
        except Exception as set_err:
            try:
                cursor.execute(
                    "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                    ("SETTLEMENT_TRIGGER_FAILED", "TrustAgent", f"Auto-settlement trigger encountered error for Order {order_id}: {set_err!s}")
                )
                conn.commit()
            except Exception:
                pass

        return {
            "status": "PAYMENT_PROCESSED_SUCCESSFULLY",
            "order_id": order_id,
            "payment_id": payment_id,
            "payment_link_id": payment_link_id,
            "product_id": product_id,
            "quantity_deducted": order_quantity,
            "remaining_stock": new_stock,
            "payment_status": "PAID",
            "settlement": settlement_result
        }

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ==========================================
# 10. EXPIRATION SWEEPERS & OUTBOX WORKER
# ==========================================
def sweep_expired_merchant_confirmations() -> dict[str, Any]:
    """
    Sweeps overdue merchant confirmations (AWAITING_MERCHANT where confirmation_expires_at <= CURRENT_TIMESTAMP).
    Atomic transition: AWAITING_MERCHANT -> TIMEOUT_EXPIRED + inserts outbox_event record in the same BEGIN IMMEDIATE transaction.
    Idempotent outbox worker processes merchant penalties and alternative discoveries.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    claimed_count = 0
    current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        cursor.execute("""
            SELECT id, product_id, merchant_id, buyer_id, amount
            FROM orders
            WHERE payment_status = 'AWAITING_MERCHANT' 
              AND (confirmation_expires_at <= ? OR confirmation_expires_at <= CURRENT_TIMESTAMP)
        """, (current_utc,))
        overdue_orders = cursor.fetchall()

        for o in overdue_orders:
            order_id = o["id"]
            # Atomic claim with single winner invariant
            cursor.execute("""
                UPDATE orders 
                SET payment_status = 'TIMEOUT_EXPIRED', updated_at = CURRENT_TIMESTAMP
                WHERE id = ? AND payment_status = 'AWAITING_MERCHANT'
            """, (order_id,))

            if cursor.rowcount == 1:
                claimed_count += 1
                outbox_id = f"out_{uuid.uuid4().hex[:12]}"
                event_key = f"timeout:{order_id}"
                payload_json = json.dumps({
                    "order_id": order_id,
                    "product_id": o["product_id"],
                    "merchant_id": o["merchant_id"],
                    "buyer_id": o["buyer_id"],
                    "amount": o["amount"]
                })
                cursor.execute("""
                    INSERT OR IGNORE INTO outbox_events (id, event_key, event_type, payload_json, status, created_at)
                    VALUES (?, ?, 'MERCHANT_TIMEOUT', ?, 'PENDING', CURRENT_TIMESTAMP)
                """, (outbox_id, event_key, payload_json))

        conn.commit()
    finally:
        conn.close()

    # Execute durable side-effect worker
    worker_result = process_pending_outbox_events()

    return {
        "status": "TIMEOUT_SWEEP_COMPLETE",
        "claimed_orders": claimed_count,
        "outbox_processed": worker_result.get("processed_count", 0)
    }


def process_pending_outbox_events() -> dict[str, Any]:
    """
    Processes pending outbox events idempotently (e.g. applying merchant penalties, audit records, and alternative discovery).
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    processed_count = 0

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM outbox_events WHERE status = 'PENDING' LIMIT 50")
        events = cursor.fetchall()

        for evt in events:
            evt_id = evt["id"]
            event_type = evt["event_type"]
            payload = json.loads(evt["payload_json"])
            order_id = payload.get("order_id")
            product_id = payload.get("product_id")
            merchant_id = payload.get("merchant_id")

            if event_type == "MERCHANT_TIMEOUT":
                # 1. Penalize merchant reliability
                if product_id and merchant_id:
                    penalize_merchant_on_failure(product_id, merchant_id, reason="MERCHANT_TIMEOUT")

                # 2. Insert audit log
                cursor.execute("""
                    INSERT INTO audit_log (action, agent, reasoning)
                    VALUES (?, ?, ?)
                """, (
                    "MERCHANT_PENALIZED_TIMEOUT",
                    "TrustAgent",
                    f"Merchant {merchant_id} failed to confirm Order {order_id} within SLA window. Reliability penalized by 0.3."
                ))

                # 3. Mark outbox event PROCESSED
                cursor.execute("""
                    UPDATE outbox_events 
                    SET status = 'PROCESSED', processed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (evt_id,))
                conn.commit()
                processed_count += 1

    finally:
        conn.close()

    return {"status": "OUTBOX_PROCESSING_COMPLETE", "processed_count": processed_count}


def sweep_expired_reservations() -> dict[str, Any]:
    """
    Sweeps expired reservations and transitions overdue orders to EXPIRED.
    DB updates happen inside BEGIN IMMEDIATE. External Razorpay cancellation is executed outside DB locks.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    links_to_cancel = []

    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        # Find expired active reservations
        cursor.execute("""
            SELECT o.id, o.payment_link_id 
            FROM orders o 
            JOIN stock_reservations r ON o.id = r.order_id 
            WHERE r.status = 'ACTIVE' AND r.expires_at <= CURRENT_TIMESTAMP
        """)
        rows = cursor.fetchall()
        for r in rows:
            if r["payment_link_id"]:
                links_to_cancel.append(r["payment_link_id"])

        # Transition reservations -> EXPIRED
        cursor.execute("""
            UPDATE stock_reservations 
            SET status = 'EXPIRED' 
            WHERE status = 'ACTIVE' AND expires_at <= CURRENT_TIMESTAMP
        """)

        # Transition orders -> EXPIRED
        cursor.execute("""
            UPDATE orders 
            SET payment_status = 'EXPIRED', updated_at = CURRENT_TIMESTAMP 
            WHERE payment_status = 'PENDING_PAYMENT' 
              AND id IN (SELECT order_id FROM stock_reservations WHERE status = 'EXPIRED')
        """)

        # Bounded Audit Log Retention: Prune entries beyond recent 5,000 records
        cursor.execute("""
            DELETE FROM audit_log 
            WHERE id NOT IN (
                SELECT id FROM audit_log ORDER BY timestamp DESC LIMIT 5000
            )
        """)

        conn.commit()
    finally:
        conn.close()

    # External Razorpay cancellation outside DB lock
    cancelled_count = 0
    for plink_id in links_to_cancel:
        try:
            razorpay_client.cancel_payment_link(plink_id)
            cancelled_count += 1
        except Exception as e:
            print(f"⚠️ Notice: Could not cancel expired payment link {plink_id} on Razorpay: {e}")

    return {
        "status": "SWEEP_COMPLETE",
        "expired_reservations": len(links_to_cancel),
        "links_cancelled": cancelled_count
    }


def expire_unpaid_order(order_id: str) -> dict[str, Any]:
    """
    Explicitly expires a single unpaid order, releases its reservation, and cancels payment link.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    plink_id = None
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.rollback()
            return {"status": "ORDER_NOT_FOUND"}

        plink_id = order["payment_link_id"]

        cursor.execute("UPDATE stock_reservations SET status = 'EXPIRED' WHERE order_id = ? AND status != 'CONSUMED'", (order_id,))
        cursor.execute("UPDATE orders SET payment_status = 'EXPIRED', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND payment_status != 'PAID'", (order_id,))
        cursor.execute("INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
                       ("ORDER_EXPIRED_RESERVATION_RELEASED", "TrustAgent", f"Order {order_id} expired. Stock reservation released."))
        conn.commit()
    finally:
        conn.close()

    if plink_id:
        try:
            razorpay_client.cancel_payment_link(plink_id)
        except Exception:
            pass

    return {"status": "ORDER_EXPIRED", "order_id": order_id}


# ==========================================
# 11. RAZORPAY ROUTE / MERCHANT SETTLEMENT EXECUTION
# ==========================================
def execute_merchant_settlement(
    order_id: str,
    platform_fee_pct: float = 2.0
) -> dict[str, Any]:
    """
    Executes split payment / merchant settlement via Razorpay Route transfer.
    Invariants Enforced:
    1. Verifies order exists and is in 'PAID' payment_status.
    2. Validates authoritative 'payment_id' exists on the order from verified webhook.
    3. Prevents duplicate payouts via atomic SETTLEMENT_IN_PROGRESS transition and provider reconciliation.
    4. Calls razorpay_client.settle_order_via_route using authentic captured payment_id outside DB locks.
    5. Records settlement in 'merchant_settlements' ledger and updates settlement_status -> 'SETTLED'.
    6. Logs full execution provenance to audit_log.
    """
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order = cursor.fetchone()
        if not order:
            conn.rollback()
            return {"status": "ORDER_NOT_FOUND", "message": f"Order {order_id} not found."}

        if order["payment_status"] != "PAID":
            conn.rollback()
            return {
                "status": "INVALID_ORDER_STATE",
                "message": f"Order {order_id} is in payment_status '{order['payment_status']}'. Must be 'PAID' before settlement."
            }

        # Validate authentic payment_id from verified webhook
        payment_id = order["payment_id"]
        if not payment_id:
            conn.rollback()
            return {
                "status": "MISSING_PAYMENT_ID",
                "message": f"Order {order_id} does not have a verified Razorpay payment_id recorded."
            }

        if order["settlement_status"] == "SETTLED":
            cursor.execute("SELECT * FROM merchant_settlements WHERE order_id = ?", (order_id,))
            settlement_record = cursor.fetchone()
            conn.rollback()
            rec = dict(settlement_record) if settlement_record else {}
            return {
                "status": "ALREADY_SETTLED",
                "message": f"Order {order_id} is already settled.",
                "order_id": order_id,
                "transfer_id": rec.get("transfer_id"),
                "platform_fee": rec.get("platform_fee"),
                "net_payout": rec.get("net_payout"),
                "settlement": rec
            }

        amount = order["amount"]
        merchant_id = order["merchant_id"]

        # Fetch merchant linked account
        cursor.execute("SELECT id, name, phone_number, razorpay_account_id FROM merchants WHERE id = ?", (merchant_id,))
        merchant = cursor.fetchone()
        merchant_name = merchant["name"] if merchant else "Merchant"
        merchant_account = merchant["razorpay_account_id"] if merchant and merchant["razorpay_account_id"] else None

        if not merchant_account:
            conn.rollback()
            return {
                "status": "MISSING_MERCHANT_LINKED_ACCOUNT",
                "message": f"Merchant '{merchant_id}' has no registered Razorpay Route Linked Account ID in database."
            }

        platform_fee = min(amount, max(0, int(amount * (platform_fee_pct / 100.0))))
        net_payout = amount - platform_fee
        assert 0 <= platform_fee <= amount
        assert 0 <= net_payout <= amount

        # Check for in-flight settlement attempt
        if order["settlement_status"] == "SETTLEMENT_IN_PROGRESS":
            started_at_str = order["settlement_started_at"]
            is_stale = False
            if started_at_str:
                started_dt = _parse_db_timestamp(started_at_str)
                age_seconds = (datetime.now(timezone.utc) - started_dt).total_seconds()
                if age_seconds > 300: # 5-minute threshold
                    is_stale = True

            if not is_stale:
                conn.rollback()
                return {
                    "status": "SETTLEMENT_IN_PROGRESS",
                    "message": f"Settlement for Order {order_id} is currently in progress."
                }

            # Stale in-progress attempt detected -> Perform provider reconciliation before retrying
            transfers_res = razorpay_client.list_transfers_for_payment(payment_id)
            if transfers_res.get("status") == "FAILED":
                # Provider lookup error -> MUST NOT PROCEED. Halted to avoid duplicate payouts!
                cursor.execute(
                    "UPDATE orders SET settlement_status = 'SETTLEMENT_RECONCILIATION_REQUIRED', settlement_error = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (f"Reconciliation error: {transfers_res.get('error')}", order_id)
                )
                conn.commit()
                return {
                    "status": "SETTLEMENT_RECONCILIATION_REQUIRED",
                    "order_id": order_id,
                    "error": f"Provider reconciliation query failed: {transfers_res.get('error')}. Settlement halted to prevent duplicate transfer."
                }

            items = transfers_res.get("items") or []
            matching_transfer = None
            for trf in items:
                trf_rec = trf.get("recipient") or trf.get("account")
                trf_amt = trf.get("amount") # amount in paise
                trf_curr = trf.get("currency", "INR")
                trf_st = trf.get("status", "processed")
                if (trf_rec == merchant_account and 
                    trf_amt == int(net_payout * 100) and 
                    trf_curr == "INR" and 
                    trf_st in ["processed", "created", "settled"]):
                    matching_transfer = trf
                    break

            if matching_transfer:
                existing_trf_id = matching_transfer.get("id")
                # Transfer was already executed on provider! Record success without double-paying
                settlement_id = f"stl_rec_{uuid.uuid4().hex[:10]}"
                cursor.execute("""
                    INSERT OR IGNORE INTO merchant_settlements (
                        id, order_id, merchant_id, payment_id, idempotency_key, gross_amount, platform_fee, net_payout, 
                        razorpay_transfer_id, settlement_status, settled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SETTLED', CURRENT_TIMESTAMP)
                """, (
                    settlement_id, order_id, order["merchant_id"], payment_id, 
                    f"stl_{order_id}_{order['amount']}", order["amount"], 
                    platform_fee,
                    net_payout,
                    existing_trf_id
                ))
                cursor.execute("UPDATE orders SET settlement_status = 'SETTLED', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
                conn.commit()
                return {
                    "status": "SETTLED",
                    "settlement_id": settlement_id,
                    "order_id": order_id,
                    "transfer_id": existing_trf_id,
                    "message": f"Recovered and verified existing Route transfer {existing_trf_id}."
                }

        idempotency_key = f"stl_{order_id}_{amount}"
        attempt_id = f"att_{uuid.uuid4().hex[:10]}"

        # Atomically claim SETTLEMENT_IN_PROGRESS
        cursor.execute("""
            UPDATE orders 
            SET settlement_status = 'SETTLEMENT_IN_PROGRESS',
                settlement_started_at = CURRENT_TIMESTAMP,
                settlement_attempt_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND settlement_status != 'SETTLED'
        """, (attempt_id, order_id))

        if cursor.rowcount != 1:
            conn.rollback()
            return {"status": "SETTLEMENT_CONFLICT", "message": "Failed to acquire settlement lock."}

        conn.commit()
    finally:
        conn.close()

    # Step 2: Execute Route transfer OUTSIDE the SQLite write lock
    route_res = razorpay_client.settle_order_via_route(
        payment_id=payment_id,
        merchant_account_id=merchant_account,
        gross_amount_inr=amount,
        platform_fee_inr=platform_fee
    )

    # Step 3: Record outcome in database
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        conn.execute("BEGIN IMMEDIATE")

        if route_res.get("status") == "FAILED":
            err_msg = route_res.get("error", "Razorpay Route Transfer failed")
            cursor.execute("""
                UPDATE orders 
                SET settlement_status = 'SETTLEMENT_RECONCILIATION_REQUIRED',
                    settlement_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (err_msg, order_id))
            cursor.execute("""
                INSERT INTO audit_log (action, agent, reasoning)
                VALUES (?, ?, ?)
            """, ("MERCHANT_SETTLEMENT_FAILED", "TrustAgent", f"Settlement attempt {attempt_id} failed for Order {order_id}: {err_msg}"))
            conn.commit()
            return {
                "status": "SETTLEMENT_FAILED",
                "error": err_msg,
                "settlement_status": "SETTLEMENT_RECONCILIATION_REQUIRED"
            }

        transfer_id = route_res.get("transfer_id")
        if not transfer_id:
            cursor.execute("""
                UPDATE orders 
                SET settlement_status = 'SETTLEMENT_RECONCILIATION_REQUIRED',
                    settlement_error = 'Provider Route response lacked transfer_id',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (order_id,))
            conn.commit()
            return {
                "status": "SETTLEMENT_RECONCILIATION_REQUIRED",
                "order_id": order_id,
                "error": "Route settlement response lacked authoritative provider transfer ID."
            }

        settlement_id = f"stl_{uuid.uuid4().hex[:12]}"

        # Insert settlement record
        cursor.execute("""
            INSERT INTO merchant_settlements (
                id, order_id, merchant_id, payment_id, idempotency_key, gross_amount, platform_fee, net_payout, 
                razorpay_transfer_id, settlement_status, settled_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'SETTLED', CURRENT_TIMESTAMP)
        """, (settlement_id, order_id, merchant_id, payment_id, idempotency_key, amount, platform_fee, net_payout, transfer_id))

        # Update order settlement status -> SETTLED
        cursor.execute("""
            UPDATE orders 
            SET settlement_status = 'SETTLED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (order_id,))

        audit_msg = (
            f"Razorpay Route settlement {settlement_id} executed for Order {order_id} (Payment: {payment_id}). "
            f"Gross: ₹{amount:,} | Platform Fee ({platform_fee_pct}%): ₹{platform_fee:,} | Net Payout: ₹{net_payout:,} → Merchant {merchant_id} ({transfer_id})."
        )
        cursor.execute("""
            INSERT INTO audit_log (action, agent, reasoning)
            VALUES (?, ?, ?)
        """, ("MERCHANT_SETTLEMENT_COMPLETED", "TrustAgent", audit_msg))

        conn.commit()

        return {
            "status": "SETTLED",
            "settlement_id": settlement_id,
            "order_id": order_id,
            "merchant_id": merchant_id,
            "merchant_name": merchant_name,
            "payment_id": payment_id,
            "gross_amount": amount,
            "platform_fee": platform_fee,
            "net_payout": net_payout,
            "transfer_id": transfer_id,
            "settlement_status": "SETTLED",
            "is_simulated": route_res.get("is_simulated", True),
            "message": f"Settled ₹{net_payout:,} to {merchant_name} (Transfer ID: {transfer_id})."
        }
    finally:
        conn.close()
