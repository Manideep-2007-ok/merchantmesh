"""
MerchantMesh - LangGraph Multi-Agent Negotiation Workflow
Orchestrates multi-turn haggling between Buyer Agent and Seller Agent with:
1. Dynamic Seller Profiling from Merchant DNA
2. Hard Code-Level Price Floor and Budget Cap Guardrails
3. Bundle & Bulk Quantity volume pricing
4. Complete turn-by-turn reasoning audit trail persisted in SQLite
"""

import hashlib
import json
import sqlite3
import uuid
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from core.negotiation_engine import (
    BuyerNegotiationConstraints,
    NegotiationTurn,
    SellerNegotiationProfile,
    build_seller_profile,
    generate_buyer_turn_llm,
    generate_seller_turn_llm,
    heuristic_seller_response,
    validate_buyer_offer,
)
from core.trust_engine import check_buyer_trust
from data.database import get_db_connection

load_dotenv()


class NegotiationState(TypedDict):
    session_id: str
    product_id: str
    merchant_id: str
    buyer_id: str
    quantity: int
    buyer_target_price: int
    buyer_max_budget: int
    product: dict[str, Any] | None
    merchant: dict[str, Any] | None
    seller_profile: dict[str, Any] | None
    buyer_constraints: dict[str, Any] | None
    buyer_trust: dict[str, Any] | None
    turns: list[dict[str, Any]]
    current_turn_index: int
    max_turns: int
    status: str  # "INITIATED", "IN_PROGRESS", "ACCEPTED", "REJECTED_FLOOR_VIOLATION", "REJECTED_BUDGET_EXCEEDED", "MAX_TURNS_REACHED", "DEADLOCK"
    final_price: int | None
    savings_amount: int | None
    savings_pct: float | None
    message: str
    audit_reasoning: str
    api_key: str | None


# ==========================================
# 1. GRAPH NODES
# ==========================================

def init_session_node(state: NegotiationState) -> dict[str, Any]:
    """Node 1: Loads product & merchant data, evaluates buyer trust, initializes profiles."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Fetch Product
        cursor.execute("SELECT * FROM products WHERE id = ?", (state["product_id"],))
        prod_row = cursor.fetchone()
        if not prod_row:
            return {
                "status": "DEADLOCK",
                "message": f"Product {state['product_id']} not found in catalog.",
                "audit_reasoning": "Product not found."
            }
        product = dict(prod_row)

        # 2. Fetch Merchant
        merchant_id = product["merchant_id"]
        cursor.execute("SELECT * FROM merchants WHERE id = ?", (merchant_id,))
        merch_row = cursor.fetchone()
        merchant = dict(merch_row) if merch_row else {
            "id": merchant_id, 
            "name": "Local Merchant", 
            "reliability_score": 5.0, 
            "merchant_dna_json": "{}"
        }

        # 3. Buyer Trust Check
        buyer_id = state.get("buyer_id", "b1")
        buyer_trust = check_buyer_trust(buyer_id)

        # 4. Build Profiles
        quantity = max(1, state.get("quantity", 1))
        seller_prof = build_seller_profile(product, merchant, quantity=quantity)

        # Buyer Constraints: Support both unit-level and total-level inputs
        raw_target = state.get("buyer_target_price")
        raw_budget = state.get("buyer_max_budget")
        unit_listed = product["listed_price"]

        if raw_target and raw_target > unit_listed and quantity > 1:
            total_target = raw_target
            unit_target = raw_target // quantity
        elif raw_target and raw_target > 0:
            unit_target = raw_target
            total_target = raw_target * quantity
        else:
            unit_target = int(unit_listed * 0.8)
            total_target = unit_target * quantity

        if raw_budget and raw_budget > unit_listed and quantity > 1:
            total_budget = raw_budget
            unit_budget = raw_budget // quantity
        elif raw_budget and raw_budget > 0:
            unit_budget = raw_budget
            total_budget = raw_budget * quantity
        else:
            unit_budget = unit_listed
            total_budget = unit_budget * quantity

        buyer_cons = BuyerNegotiationConstraints(
            buyer_id=buyer_id,
            target_price=unit_target,
            max_budget=unit_budget,
            quantity=quantity,
            total_target_price=total_target,
            total_max_budget=total_budget,
            urgency="medium",
            preferred_payment="UPI"
        )

        return {
            "merchant_id": merchant_id,
            "product": product,
            "merchant": merchant,
            "seller_profile": seller_prof.model_dump(),
            "buyer_constraints": buyer_cons.model_dump(),
            "buyer_trust": buyer_trust,
            "status": "IN_PROGRESS",
            "current_turn_index": 0,
            "turns": []
        }
    finally:
        conn.close()


def buyer_turn_node(state: NegotiationState) -> dict[str, Any]:
    """Node 2: Buyer Agent generates an offer or counter-offer."""
    if state["status"] in ["ACCEPTED", "REJECTED_FLOOR_VIOLATION", "DEADLOCK", "MAX_TURNS_REACHED"]:
        return {}

    turns_raw = state.get("turns", [])
    history = [NegotiationTurn(**t) for t in turns_raw]
    constraints = BuyerNegotiationConstraints(**state["buyer_constraints"])
    seller_prof = SellerNegotiationProfile(**state["seller_profile"])
    turn_idx = state.get("current_turn_index", 0) + 1

    # Find seller's last offer if any
    seller_turns = [t for t in history if t.speaker == "SELLER"]
    last_seller_counter = seller_turns[-1].proposed_price if seller_turns else seller_prof.total_listed_price

    # Generate Buyer Turn
    buyer_out = generate_buyer_turn_llm(
        history=history,
        constraints=constraints,
        seller_last_counter=last_seller_counter,
        seller_flexibility=seller_prof.flexibility,
        api_key=state.get("api_key")
    )

    # Convert to standard turn
    turn_entry = NegotiationTurn(
        turn_number=len(history) + 1,
        speaker="BUYER",
        action=buyer_out.action,
        proposed_price=buyer_out.offer_price,
        message=buyer_out.message,
        internal_reasoning=buyer_out.internal_reasoning,
        guardrail_status="PASSED"
    )

    updated_turns = list(turns_raw)
    updated_turns.append(turn_entry.model_dump())

    return {
        "turns": updated_turns,
        "current_turn_index": turn_idx
    }


def buyer_guardrail_node(state: NegotiationState) -> dict[str, Any]:
    """Node 3: Strict Code-Level Guardrail for Buyer Agent."""
    turns_raw = state.get("turns", [])
    if not turns_raw:
        return {}

    last_turn = turns_raw[-1]
    if last_turn["speaker"] != "BUYER":
        return {}

    constraints = BuyerNegotiationConstraints(**state["buyer_constraints"])
    is_valid, reason = validate_buyer_offer(last_turn["proposed_price"], constraints.total_max_budget)

    if not is_valid:
        print(f"🛑 Code Guardrail Intercepted Buyer Turn: {reason}")
        raw_price = last_turn["proposed_price"] if last_turn["proposed_price"] > 0 else constraints.total_target_price
        last_turn["proposed_price"] = max(1, min(constraints.total_max_budget, raw_price))
        last_turn["guardrail_status"] = "CLAMPED_BY_CODE_GUARDRAIL"
    return {"turns": turns_raw}


def seller_turn_node(state: NegotiationState) -> dict[str, Any]:
    """Node 4: Seller Agent evaluates buyer offer and formulates response."""
    # Guard: skip if negotiation already reached a terminal state or has no turns
    if state.get("status") in ["ACCEPTED", "REJECTED_FLOOR_VIOLATION", "DEADLOCK", "MAX_TURNS_REACHED", "REJECTED_BUDGET_EXCEEDED"]:
        return {}

    turns_raw = state.get("turns", [])
    history = [NegotiationTurn(**t) for t in turns_raw]

    buyer_turns = [t for t in history if t.speaker == "BUYER"]
    if not buyer_turns:
        return {}
    last_buyer_turn = buyer_turns[-1]
    buyer_offer = last_buyer_turn.proposed_price

    seller_prof = SellerNegotiationProfile(**state["seller_profile"])

    # If buyer walked away, handle deadlock
    if last_buyer_turn.action == "WALK_AWAY":
        seller_out = heuristic_seller_response(buyer_offer, seller_prof, state["current_turn_index"])
        turn_entry = NegotiationTurn(
            turn_number=len(history) + 1,
            speaker="SELLER",
            action="REJECT",
            proposed_price=seller_prof.total_floor_price,
            message="No problem bhaiya. Agar budget adjust ho sake toh zaroor batana!",
            internal_reasoning="Buyer chose to walk away. Closed negotiation politely.",
            guardrail_status="PASSED"
        )
        updated_turns = list(turns_raw)
        updated_turns.append(turn_entry.model_dump())
        return {
            "turns": updated_turns,
            "status": "DEADLOCK",
            "message": "Negotiation concluded without a deal (Buyer walked away).",
            "audit_reasoning": "Buyer reached max budget and walked away."
        }

    # If buyer accepted seller's previous offer
    if last_buyer_turn.action == "ACCEPT":
        seller_turns = [t for t in history if t.speaker == "SELLER"]
        last_seller_counter = seller_turns[-1].proposed_price if seller_turns else seller_prof.total_listed_price
        
        # Security Invariant: An acceptance can ONLY bind to the seller's authentic prior counter price
        # The buyer cannot dictate or inject an arbitrary lower price (e.g. ₹1) on acceptance.
        agreed_deal_price = max(seller_prof.total_floor_price, last_seller_counter)

        turn_entry = NegotiationTurn(
            turn_number=len(history) + 1,
            speaker="SELLER",
            action="ACCEPT",
            proposed_price=agreed_deal_price,
            message=f"Awesome! Deal confirmed at ₹{agreed_deal_price:,}. Generating Razorpay payment link... 🛍️",
            internal_reasoning=f"Buyer accepted seller counter of ₹{agreed_deal_price}. Proceeding to order creation.",
            guardrail_status="PASSED"
        )
        updated_turns = list(turns_raw)
        updated_turns.append(turn_entry.model_dump())
        
        savings = seller_prof.total_listed_price - agreed_deal_price
        savings_pct = round((savings / seller_prof.total_listed_price) * 100.0, 1) if seller_prof.total_listed_price > 0 else 0.0

        return {
            "turns": updated_turns,
            "status": "ACCEPTED",
            "final_price": agreed_deal_price,
            "savings_amount": savings,
            "savings_pct": savings_pct,
            "message": f"🎉 Deal closed successfully at ₹{agreed_deal_price:,}! You saved ₹{savings:,} ({savings_pct}% off listed price).",
            "audit_reasoning": f"Deal accepted at ₹{agreed_deal_price}. Margin protected above floor ₹{seller_prof.total_floor_price}."
        }

    # Generate Seller Turn
    seller_out = generate_seller_turn_llm(
        history=history,
        profile=seller_prof,
        buyer_last_offer=buyer_offer
    )

    turn_entry = NegotiationTurn(
        turn_number=len(history) + 1,
        speaker="SELLER",
        action=seller_out.action,
        proposed_price=seller_out.counter_price,
        message=seller_out.message,
        internal_reasoning=seller_out.internal_reasoning,
        guardrail_status="PASSED"
    )

    updated_turns = list(turns_raw)
    updated_turns.append(turn_entry.model_dump())

    return {"turns": updated_turns}


def seller_guardrail_node(state: NegotiationState) -> dict[str, Any]:
    """
    Node 5: CRITICAL CODE-LEVEL GUARDRAIL for Seller Agent.
    Strictly verifies that NO deal is accepted and NO counter is proposed below the hard floor price.
    """
    turns_raw = state.get("turns", [])
    if not turns_raw:
        return {}

    last_turn = turns_raw[-1]
    if last_turn["speaker"] != "SELLER":
        return {}

    seller_prof = SellerNegotiationProfile(**state["seller_profile"])
    floor_price = seller_prof.total_floor_price
    listed_price = seller_prof.total_listed_price

    # 1. HARD FLOOR CHECK & REVERSION
    if last_turn["proposed_price"] < floor_price:
        spread = listed_price - floor_price
        if spread > 0:
            safe_counter = min(listed_price, floor_price + max(50, int(spread * 0.10)))
        else:
            safe_counter = floor_price
        print(f"🛑 CRITICAL CODE GUARDRAIL: Seller attempted to counter/accept at ₹{last_turn['proposed_price']}, below floor ₹{floor_price}. Clamped to safe price ₹{safe_counter}.")
        last_turn["proposed_price"] = safe_counter
        last_turn["action"] = "COUNTER"
        last_turn["guardrail_status"] = "OVERRIDDEN_TO_SAFE_COUNTER"
        
        buyer_turns = [t for t in turns_raw if t["speaker"] == "BUYER"]
        last_buyer_msg = buyer_turns[-1].get("message", "").lower() if buyer_turns else ""
        is_hindi = any(word in last_buyer_msg for word in ['bhaiya', 'kam', 'karo', 'thoda', 'sahi', 'bhai', 'chahiye', 'kardo', 'dena'])
        
        if is_hindi:
            last_turn["message"] = f"Bhaiya is price pe possible nahi hai. Best price ₹{safe_counter:,} final kar sakte hain."
        else:
            last_turn["message"] = f"Sir/Ma'am, I cannot accept that offer. The best price I can offer is ₹{safe_counter:,}."

        # Hard invariant: Sub-floor proposals NEVER remain in ACCEPTED state
        return {
            "turns": turns_raw,
            "status": "IN_PROGRESS",
            "final_price": None
        }

    # 2. Check if Seller Accepted
    if last_turn["action"] == "ACCEPT":
        deal_price = last_turn["proposed_price"]
        # Double check deal price >= floor
        if deal_price >= floor_price:
            savings = listed_price - deal_price
            savings_pct = round((savings / listed_price) * 100.0, 1) if listed_price > 0 else 0.0
            return {
                "turns": turns_raw,
                "status": "ACCEPTED",
                "final_price": deal_price,
                "savings_amount": savings,
                "savings_pct": savings_pct,
                "message": f"🎉 Deal closed successfully at ₹{deal_price:,}! You saved ₹{savings:,} ({savings_pct}% off listed price).",
                "audit_reasoning": f"Deal accepted at ₹{deal_price}. Verified margin protected by code guardrail."
            }
        else:
            # Sub-floor acceptance exploit prevention: Revert to COUNTER at floor price
            last_turn["proposed_price"] = floor_price
            last_turn["action"] = "COUNTER"
            last_turn["guardrail_status"] = "OVERRIDDEN_TO_SAFE_COUNTER"
            last_turn["message"] = f"Sir/Ma'am, I cannot accept that offer. The best price I can offer is ₹{floor_price:,}."
            return {
                "turns": turns_raw,
                "status": "IN_PROGRESS",
                "final_price": None
            }

    # 3. Check for Extreme Lowball Rejection
    buyer_last_turn = [t for t in turns_raw if t["speaker"] == "BUYER"][-1]
    if last_turn["action"] == "REJECT" and buyer_last_turn["proposed_price"] < floor_price * 0.70:
        return {
            "turns": turns_raw,
            "status": "REJECTED_FLOOR_VIOLATION",
            "message": f"❌ Negotiation ended: Offered price ₹{buyer_last_turn['proposed_price']:,} is below the merchant's acceptable price range.",
            "audit_reasoning": f"Hard floor violation: Buyer offer ₹{buyer_last_turn['proposed_price']} was below threshold. Rejected."
        }

    return {"turns": turns_raw}


def audit_and_persist_node(state: NegotiationState) -> dict[str, Any]:
    """
    Node 6: Persists complete negotiation history into SQLite 'negotiations' table
    and writes security and trust audit reasoning into 'audit_log' table.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        session_id = state.get("session_id") or f"neg_{uuid.uuid4().hex[:8]}"
        product_id = state.get("product_id", "p1")
        buyer_id = state.get("buyer_id", "b1")
        turns_json = json.dumps(state.get("turns", []))
        final_price = state.get("final_price")
        outcome = state.get("status", "COMPLETED")

        quantity = state.get("quantity", 1)

        # 0. Ensure ephemeral buyer exists in buyers table to satisfy foreign key constraint
        cursor.execute("SELECT id FROM buyers WHERE id = ?", (buyer_id,))
        if not cursor.fetchone():
            phone_candidate = f"+919{int(hashlib.sha256(buyer_id.encode('utf-8')).hexdigest()[:8], 16) % 1000000000:09d}"
            for attempt in range(20):
                try:
                    cursor.execute("INSERT INTO buyers (id, phone_number) VALUES (?, ?)", (buyer_id, phone_candidate))
                    break
                except sqlite3.IntegrityError:
                    phone_candidate = f"+919{int(hashlib.sha256(f'{buyer_id}_{attempt}'.encode()).hexdigest()[:8], 16) % 1000000000:09d}"

        # 1. Insert/Update negotiations table with explicit conflict update
        cursor.execute(
            """
            INSERT INTO negotiations (id, product_id, buyer_id, quantity, turns_json, final_price, outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                quantity = excluded.quantity,
                turns_json = excluded.turns_json,
                final_price = excluded.final_price,
                outcome = excluded.outcome
            """,
            (session_id, product_id, buyer_id, quantity, turns_json, final_price, outcome)
        )

        # 2. Insert into audit_log
        audit_action = f"NEGOTIATION_{outcome}"
        agent_name = "NegotiationAgent"
        audit_reasoning = state.get("audit_reasoning") or f"Negotiation finished with status {outcome}. Final price: {final_price}."

        cursor.execute(
            "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
            (audit_action, agent_name, audit_reasoning)
        )

        conn.commit()
    except Exception as e:
        print(f"⚠️ Negotiation DB Persist error: {e}")
    finally:
        conn.close()

    return {}


# ==========================================
# 2. CONDITIONAL ROUTING & GRAPH COMPILATION
# ==========================================

def max_turns_handler_node(state: NegotiationState) -> dict[str, Any]:
    """
    Node: Handles MAX_TURNS_REACHED terminal state.
    If the buyer's last offer meets the seller's floor price and is within budget, close deal at mutual agreed price.
    Otherwise, log DEADLOCK cleanly.
    """
    turns = state.get("turns", [])
    seller_prof_raw = state.get("seller_profile", {})
    buyer_con_raw = state.get("buyer_constraints", {})
    max_turns = state.get("max_turns", 4)

    if seller_prof_raw and buyer_con_raw and turns:
        buyer_turns = [t for t in turns if t.get("speaker") == "BUYER"]
        seller_turns = [t for t in turns if t.get("speaker") == "SELLER"]
        if buyer_turns and seller_turns:
            floor = seller_prof_raw.get("total_floor_price", 0) if isinstance(seller_prof_raw, dict) else getattr(seller_prof_raw, "total_floor_price", 0)
            listed_price = seller_prof_raw.get("total_listed_price", 1000) if isinstance(seller_prof_raw, dict) else getattr(seller_prof_raw, "total_listed_price", 1000)
            budget = buyer_con_raw.get("total_max_budget", 50000) if isinstance(buyer_con_raw, dict) else getattr(buyer_con_raw, "total_max_budget", 50000)

            last_buyer_price = buyer_turns[-1].get("proposed_price", 0)
            last_seller_price = seller_turns[-1].get("proposed_price", listed_price)

            # If buyer offer is above floor and seller offer is within budget, accept at seller's best counter
            if last_buyer_price >= floor and last_seller_price <= budget:
                agreed = min(last_seller_price, max(floor, last_buyer_price))
                savings = listed_price - agreed
                savings_pct = round((savings / listed_price) * 100.0, 1) if listed_price > 0 else 0.0

                closing_turn = {
                    "turn_number": len(turns) + 1,
                    "speaker": "SELLER",
                    "action": "ACCEPT",
                    "proposed_price": agreed,
                    "message": f"Final compromise agreed at ₹{agreed:,}. Deal locked! 🤝",
                    "internal_reasoning": f"Closed at ₹{agreed} on final turn compromise.",
                    "guardrail_status": "PASSED"
                }
                updated_turns = list(turns) + [closing_turn]
                return {
                    "turns": updated_turns,
                    "status": "ACCEPTED",
                    "final_price": agreed,
                    "savings_amount": savings,
                    "savings_pct": savings_pct,
                    "message": f"🎉 Deal closed successfully at ₹{agreed:,}! You saved ₹{savings:,} ({savings_pct}% off listed price).",
                    "audit_reasoning": f"Deal accepted at ₹{agreed} on final turn {max_turns}. Margin protected."
                }

    return {
        "status": "DEADLOCK",
        "message": "Negotiation reached maximum turn limit without agreement.",
        "audit_reasoning": f"Max turns ({max_turns}) reached without agreement. No deal closed."
    }


def _route_after_seller(state: NegotiationState) -> str:
    """
    Routes based on negotiation progress and safety status.
    PURE FUNCTION: only reads state, never mutates it (LangGraph requirement).
    """
    status = state.get("status", "IN_PROGRESS")
    if status in ["ACCEPTED", "REJECTED_FLOOR_VIOLATION", "REJECTED_BUDGET_EXCEEDED", "DEADLOCK"]:
        return "audit_and_persist"

    turn_idx = state.get("current_turn_index", 0)
    max_turns = state.get("max_turns", 4)

    if turn_idx >= max_turns:
        return "max_turns_handler"

    return "buyer_turn"


# Construct LangGraph StateGraph
workflow = StateGraph(NegotiationState)

workflow.add_node("init_session", init_session_node)
workflow.add_node("buyer_turn", buyer_turn_node)
workflow.add_node("buyer_guardrail", buyer_guardrail_node)
workflow.add_node("seller_turn", seller_turn_node)
workflow.add_node("seller_guardrail", seller_guardrail_node)
workflow.add_node("max_turns_handler", max_turns_handler_node)
workflow.add_node("audit_and_persist", audit_and_persist_node)

workflow.add_edge(START, "init_session")
workflow.add_edge("init_session", "buyer_turn")
workflow.add_edge("buyer_turn", "buyer_guardrail")
workflow.add_edge("buyer_guardrail", "seller_turn")
workflow.add_edge("seller_turn", "seller_guardrail")

workflow.add_conditional_edges("seller_guardrail", _route_after_seller, {
    "audit_and_persist": "audit_and_persist",
    "buyer_turn": "buyer_turn",
    "max_turns_handler": "max_turns_handler"
})

workflow.add_edge("max_turns_handler", "audit_and_persist")
workflow.add_edge("audit_and_persist", END)

negotiation_graph = workflow.compile()


# ==========================================
# 3. PUBLIC ENTRYPOINTS
# ==========================================

def run_negotiation(
    product_id: str,
    buyer_target_price: int | None = None,
    buyer_max_budget: int | None = None,
    quantity: int = 1,
    buyer_id: str = "b1",
    max_turns: int = 4,
    api_key: str | None = None
) -> dict[str, Any]:
    """
    Public entrypoint to run end-to-end multi-agent negotiation via LangGraph.
    """
    session_id = f"neg_{uuid.uuid4().hex[:8]}"

    initial_state: NegotiationState = {
        "session_id": session_id,
        "product_id": product_id,
        "merchant_id": "",
        "buyer_id": buyer_id,
        "quantity": quantity,
        "buyer_target_price": buyer_target_price or 0,
        "buyer_max_budget": buyer_max_budget or 0,
        "product": None,
        "merchant": None,
        "seller_profile": None,
        "buyer_constraints": None,
        "buyer_trust": None,
        "turns": [],
        "current_turn_index": 0,
        "max_turns": max_turns,
        "status": "INITIATED",
        "final_price": None,
        "savings_amount": 0,
        "savings_pct": 0.0,
        "message": "",
        "audit_reasoning": "",
        "api_key": api_key
    }

    try:
        final_state = negotiation_graph.invoke(initial_state)

        safe_seller_profile = dict(final_state.get("seller_profile") or {})
        safe_seller_profile.pop("floor_price", None)
        safe_seller_profile.pop("total_floor_price", None)

        return {
            "session_id": final_state["session_id"],
            "status": final_state["status"],
            "outcome": final_state["status"],
            "product_id": final_state["product_id"],
            "product_name": (final_state.get("product") or {}).get("product_name", "Product"),
            "merchant_name": (final_state.get("merchant") or {}).get("name", "Merchant"),
            "quantity": final_state["quantity"],
            "final_price": final_state["final_price"],
            "savings_amount": final_state.get("savings_amount", 0),
            "savings_pct": final_state.get("savings_pct", 0.0),
            "total_turns": len(final_state.get("turns", [])),
            "turns": final_state.get("turns", []),
            "message": final_state.get("message", ""),
            "audit_reasoning": final_state.get("audit_reasoning", ""),
            "seller_profile": safe_seller_profile,
            "buyer_constraints": final_state.get("buyer_constraints")
        }
    except Exception as e:
        print(f"❌ Error executing Negotiation Agent: {e}")
        raise e


def stream_negotiation(
    product_id: str,
    buyer_target_price: int | None = None,
    buyer_max_budget: int | None = None,
    quantity: int = 1,
    buyer_id: str = "b1",
    max_turns: int = 4,
    api_key: str | None = None
):
    """
    Generator yielding real-time turn-by-turn events as LangGraph executes.
    Yields dicts with event: 'init' | 'turn' | 'complete' | 'error'.
    """
    session_id = f"neg_{uuid.uuid4().hex[:8]}"

    initial_state: NegotiationState = {
        "session_id": session_id,
        "product_id": product_id,
        "merchant_id": "",
        "buyer_id": buyer_id,
        "quantity": quantity,
        "buyer_target_price": buyer_target_price or 0,
        "buyer_max_budget": buyer_max_budget or 0,
        "product": None,
        "merchant": None,
        "seller_profile": None,
        "buyer_constraints": None,
        "buyer_trust": None,
        "turns": [],
        "current_turn_index": 0,
        "max_turns": max_turns,
        "status": "INITIATED",
        "final_price": None,
        "savings_amount": 0,
        "savings_pct": 0.0,
        "message": "",
        "audit_reasoning": "",
        "api_key": api_key
    }

    current_state = dict(initial_state)
    last_yielded_turn_count = 0

    try:
        for step in negotiation_graph.stream(initial_state):
            for node_name, node_output in step.items():
                if node_output:
                    current_state.update(node_output)

                if node_name == "init_session":
                    yield {
                        "event": "init",
                        "session_id": session_id,
                        "product_name": (current_state.get("product") or {}).get("product_name", "Product"),
                        "merchant_name": (current_state.get("merchant") or {}).get("name", "Merchant"),
                        "listed_price": (current_state.get("product") or {}).get("listed_price", 0),
                        "quantity": quantity
                    }

                turns = current_state.get("turns", [])
                if len(turns) > last_yielded_turn_count:
                    for t in turns[last_yielded_turn_count:]:
                        yield {
                            "event": "turn",
                            "turn": t,
                            "turn_number": t.get("turn_number"),
                            "speaker": t.get("speaker"),
                            "action": t.get("action"),
                            "proposed_price": t.get("proposed_price"),
                            "message": t.get("message"),
                            "guardrail_status": t.get("guardrail_status", "PASSED"),
                            "internal_reasoning": t.get("internal_reasoning", "")
                        }
                    last_yielded_turn_count = len(turns)

        safe_seller_profile = dict(current_state.get("seller_profile") or {})
        safe_seller_profile.pop("floor_price", None)
        safe_seller_profile.pop("total_floor_price", None)

        turns_final = current_state.get("turns", [])
        terminal_logs = [
            f"[LangGraph] Live Streaming A2A Negotiation completed. Session: {session_id}",
            f"[Agent] Product: {(current_state.get('product') or {}).get('product_name', 'Product')} | Quantity: {quantity}",
        ]
        for t in turns_final:
            terminal_logs.append(
                f"[Turn {t.get('turn_number', '?')}] {t.get('speaker', '?')} -> {t.get('action', '?')} @ ₹{t.get('proposed_price', 0):,} | Guardrail: {t.get('guardrail_status', 'PASSED')}"
            )
        terminal_logs.append(f"[Agent] Outcome: {current_state.get('status')} | Final Price: ₹{current_state.get('final_price', 'N/A')}")

        yield {
            "event": "complete",
            "session_id": current_state["session_id"],
            "status": current_state.get("status", "COMPLETED"),
            "outcome": current_state.get("status", "COMPLETED"),
            "product_id": current_state.get("product_id"),
            "product_name": (current_state.get("product") or {}).get("product_name", "Product"),
            "merchant_name": (current_state.get("merchant") or {}).get("name", "Merchant"),
            "quantity": current_state.get("quantity", 1),
            "final_price": current_state.get("final_price"),
            "savings_amount": current_state.get("savings_amount", 0),
            "savings_pct": current_state.get("savings_pct", 0.0),
            "total_turns": len(turns_final),
            "turns": turns_final,
            "conversation": [
                {
                    "speaker": t.get("speaker"),
                    "action": t.get("action"),
                    "price": t.get("proposed_price"),
                    "message": t.get("message"),
                    "guardrail": t.get("guardrail_status", "PASSED"),
                }
                for t in turns_final
            ],
            "message": current_state.get("message", ""),
            "audit_reasoning": current_state.get("audit_reasoning", ""),
            "terminal_logs": terminal_logs,
            "seller_profile": safe_seller_profile,
            "buyer_constraints": current_state.get("buyer_constraints")
        }
    except Exception as e:
        yield {
            "event": "error",
            "error": str(e)
        }


