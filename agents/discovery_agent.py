"""
MerchantMesh - LangGraph Discovery Agent
Orchestrates buyer query understanding, hybrid candidate retrieval,
LLM Personal Shopper reasoning, edge-case evaluation, and audit logging.
"""

from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from core.config import CONFIG
from core.discovery_engine import (
    llm_personal_shopper_rerank,
    retrieve_candidates,
    score_candidate_heuristics,
)
from core.market_intelligence import get_trending_insights
from core.query_parser import ParsedQuery, parse_buyer_query
from core.trust_engine import check_buyer_trust
from data.database import get_db_connection

load_dotenv()


class DiscoveryState(TypedDict):
    raw_query: str
    chat_history: list[dict[str, str]] | None
    buyer_id: str | None
    session_id: str | None
    buyer_trust: dict[str, Any] | None
    parsed_query: dict[str, Any] | None
    candidates: list[dict[str, Any]]
    ranked_products: list[dict[str, Any]]
    status: str
    message: str
    closest_match: dict[str, Any] | None
    suggested_budget: int | None
    trending_suggestions: list[str]
    audit_reasoning: str


def parse_and_profile_node(state: DiscoveryState) -> dict[str, Any]:
    """Node 1: Parses buyer query and checks buyer trust history if buyer_id provided."""
    raw_q = state.get("raw_query", "")
    buyer_id = state.get("buyer_id")
    history = state.get("chat_history")
    
    parsed = parse_buyer_query(raw_q, chat_history=history)
    buyer_trust = check_buyer_trust(buyer_id) if buyer_id else {"is_safe": True, "warning": None}
    

    if parsed.intent == "greeting" or (not parsed.search_keywords and parsed.category == "General"):
        return {
            "parsed_query": parsed.model_dump(),
            "buyer_trust": buyer_trust,
            "status": "GREETING",
            "message": "Hello! I am your MerchantMesh Buyer Agent. What are you looking for today?"
        }


    return {
        "parsed_query": parsed.model_dump(),
        "buyer_trust": buyer_trust,
        "status": "PARSED"
    }


def retrieve_candidates_node(state: DiscoveryState) -> dict[str, Any]:
    """Node 2: Executes Hidden-Floor SQL retrieval & heuristic scoring."""
    parsed_dict = state["parsed_query"] or {}
    parsed = ParsedQuery(**parsed_dict)
    session_id = state.get("session_id")
    
    # Step 1: Standard Hidden-Floor candidate retrieval
    candidates = retrieve_candidates(parsed, include_all_for_fallback=False, session_id=session_id)

    # Score all candidates
    for c in candidates:
        c["pre_score"] = score_candidate_heuristics(c, parsed)

    viable = [c for c in candidates if c.get("pre_score", 0) > 0.0 and c.get("relevance", 0) >= CONFIG.min_relevance_threshold]

    # If no viable candidates within budget, check fallback
    if not viable:
        all_candidates = retrieve_candidates(parsed, include_all_for_fallback=True, session_id=session_id)
        for c in all_candidates:
            c["pre_score"] = score_candidate_heuristics(c, parsed)
        
        relevant_all = [c for c in all_candidates if c.get("pre_score", 0) > 0.0 and c.get("relevance", 0) >= CONFIG.min_relevance_threshold]
        
        # Edge Case: Budget Too Low
        if relevant_all and parsed.max_budget is not None:
            matching_items = sorted(relevant_all, key=lambda c: c["pre_score"], reverse=True)
            closest = matching_items[0]
            listed = closest["listed_price"]
            
            # Base starting negotiation budget strictly on buyer-visible listed price (e.g. 15% discount room)
            # Never derive or expose suggestions from confidential merchant floor prices
            suggested_start = max(int(listed * 0.85), (parsed.max_budget or 0) + 100)
            suggested_start = min(suggested_start, listed)
            
            msg = (
                f"⚠️ Budget Alert: Your budget of ₹{parsed.max_budget:,} is too low for this item. "
                f"The closest matching item '{closest['product_name']}' is listed at ₹{closest['listed_price']:,}. "
                f"If you can increase your budget to around ₹{suggested_start:,}, I can try to negotiate a deal with the seller for you."
            )
            return {
                "status": "BUDGET_TOO_LOW",
                "candidates": [],
                "ranked_products": matching_items[:3],
                "closest_match": closest,
                "suggested_budget": suggested_start,
                "message": msg,
                "audit_reasoning": f"Budget ₹{parsed.max_budget} is lower than viable items. Suggested starting negotiation budget is ₹{suggested_start} (derived from listed price ₹{listed})."
            }

        # Edge Case: Zero Results
        trending = get_trending_insights(limit=3)
        return {
            "status": "NO_RESULTS",
            "candidates": [],
            "ranked_products": [],
            "trending_suggestions": trending,
            "message": f"🔍 No matching products found for '{state['raw_query']}'. Check our trending categories!",
            "audit_reasoning": f"Zero candidates matched query '{state['raw_query']}' in catalog."
        }

    return {
        "status": "CANDIDATES_RETRIEVED",
        "candidates": viable
    }


def personal_shopper_rerank_node(state: DiscoveryState) -> dict[str, Any]:
    """Node 3: LLM Personal Shopper Contextual Re-Ranking."""
    if state["status"] in ["BUDGET_TOO_LOW", "NO_RESULTS"]:
        return {}

    parsed = ParsedQuery(**(state["parsed_query"] or {}))
    candidates = state["candidates"] or []
    
    top_ranked = llm_personal_shopper_rerank(candidates, parsed)

    reasoning_summary = f"Curated {len(top_ranked)} recommendations from {len(candidates)} candidates based on cultural context, hidden floors, and seller ratings."
    
    return {
        "ranked_products": top_ranked,
        "status": "SUCCESS",
        "message": f"Found {len(top_ranked)} curated recommendations matching your search.",
        "audit_reasoning": reasoning_summary
    }


def audit_logging_node(state: DiscoveryState) -> dict[str, Any]:
    """Node 4: Writes discovery decision and reasoning to the audit_log database table."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        action = f"DISCOVERY_SEARCH_{state.get('status', 'COMPLETED')}"
        agent = "DiscoveryAgent"
        reasoning = state.get("audit_reasoning", "Completed product search and ranking.")
        
        cursor.execute(
            "INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)",
            (action, agent, reasoning)
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️ Audit log write error: {e}")
    finally:
        conn.close()

    return {}



def _route_after_parse(state: DiscoveryState) -> str:
    parsed = state.get("parsed_query") or {}
    if parsed.get("intent") == "greeting" or (not parsed.get("search_keywords") and parsed.get("category") == "General"):
        state["status"] = "GREETING"
        state["message"] = "Hello! I am your MerchantMesh Buyer Agent. What are you looking for today?"
        return "audit_logging"
    return "retrieve_candidates"

def _route_after_retrieve(state: DiscoveryState) -> str:
    """Conditional router based on retrieval outcome."""
    if state.get("status") in ["BUDGET_TOO_LOW", "NO_RESULTS"]:
        return "audit_logging"
    return "personal_shopper_rerank"


# Construct LangGraph Workflow
workflow = StateGraph(DiscoveryState)

workflow.add_node("parse_and_profile", parse_and_profile_node)
workflow.add_node("retrieve_candidates", retrieve_candidates_node)
workflow.add_node("personal_shopper_rerank", personal_shopper_rerank_node)
workflow.add_node("audit_logging", audit_logging_node)

workflow.add_edge(START, "parse_and_profile")
workflow.add_conditional_edges("parse_and_profile", _route_after_parse, {
    "audit_logging": "audit_logging",
    "retrieve_candidates": "retrieve_candidates"
})
workflow.add_conditional_edges("retrieve_candidates", _route_after_retrieve, {
    "audit_logging": "audit_logging",
    "personal_shopper_rerank": "personal_shopper_rerank"
})
workflow.add_edge("personal_shopper_rerank", "audit_logging")
workflow.add_edge("audit_logging", END)

discovery_graph = workflow.compile()


def _sanitize_buyer_product(p: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strips confidential merchant floor fields from buyer-facing product representations."""
    if not p:
        return None
    cleaned = dict(p)
    for k in ["floor_price", "total_floor", "unit_floor", "total_floor_price", "min_floor"]:
        cleaned.pop(k, None)
    return cleaned


def run_discovery_agent(query: str, buyer_id: str | None = None, chat_history: list[dict[str, str]] | None = None, session_id: str | None = None) -> dict[str, Any]:
    """
    Public entrypoint to run the Discovery Agent via LangGraph.
    """
    initial_state: DiscoveryState = {
        "raw_query": query,
        "chat_history": chat_history,
        "buyer_id": buyer_id,
        "session_id": session_id,
        "buyer_trust": None,
        "parsed_query": None,
        "candidates": [],
        "ranked_products": [],
        "status": "INITIATED",
        "message": "",
        "closest_match": None,
        "suggested_budget": None,
        "trending_suggestions": [],
        "audit_reasoning": ""
    }

    final_state = discovery_graph.invoke(initial_state)
    parsed_q = final_state.get("parsed_query") or {}

    sanitized_ranked = [_sanitize_buyer_product(p) for p in (final_state.get("ranked_products") or [])]
    sanitized_closest = _sanitize_buyer_product(final_state.get("closest_match"))

    return {
        "status": final_state["status"],
        "message": final_state["message"],
        "parsed_query": parsed_q,
        "is_degraded": parsed_q.get("is_degraded", False),
        "extraction_source": parsed_q.get("extraction_source", "ai"),
        "ranked_products": sanitized_ranked,
        "closest_match": sanitized_closest,
        "suggested_budget": final_state["suggested_budget"],
        "trending_suggestions": final_state["trending_suggestions"],
        "buyer_trust": final_state["buyer_trust"]
    }
