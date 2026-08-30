"""
MerchantMesh - Two-Sided AI Discovery & Matchmaking Engine
Features:
1. Hidden-Floor Budget Matching (discovers items where listed > budget but floor <= budget)
2. Hybrid Retrieval (SQL Predicate Pushdown + Normalized Token & Taxonomy Matching)
3. Configurable Multi-Factor Ranking & Merchant DNA Matchmaking
4. LLM 'Personal Shopper' Re-Ranker with Contextual & Cultural Reasoning
5. Dynamic Availability Badging (✅ ⚠️ ❓) & Time-Decay Synchronization
6. Graceful Edge Case Handlers (Budget Too Low, Zero Matches)
"""

import json
import os
import re
import sqlite3
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from core.config import CONFIG, DB_PATH
from core.query_parser import ParsedQuery
from core.trust_engine import update_product_confidence

load_dotenv()

def _compute_text_token_similarity(query_text: str, candidate_text: str) -> float:
    """Computes token-level Jaccard and n-gram overlap similarity between query and candidate."""
    query_norm = query_text.lower().replace("-", "")
    cand_norm = candidate_text.lower().replace("-", "")
    q_tokens = set(re.findall(r'\b\w+\b', query_norm))
    c_tokens = set(re.findall(r'\b\w+\b', cand_norm))
    if not q_tokens or not c_tokens:
        return 0.0
    intersection = q_tokens.intersection(c_tokens)
    union = q_tokens.union(c_tokens)
    return len(intersection) / len(union) if union else 0.0


def get_availability_indicator(confidence: float, stock_quantity: int) -> tuple[str, str]:
    """
    Computes availability badges using configurable confidence thresholds.
    """
    if stock_quantity <= 0:
        return "❌ Out of Stock", "Item currently unavailable"
    elif confidence >= CONFIG.high_confidence_threshold and stock_quantity > 1:
        return "✅ Available (High Trust)", "Stock verified recently with merchant"
    elif confidence >= CONFIG.medium_confidence_threshold:
        return "⚠️ Likely Available", "Stock check recommended during negotiation"
    else:
        return "❓ Stale Stock (Pending Confirmation)", "Listing is stale; agent will confirm live with merchant"


class ReRankedItem(BaseModel):
    product_id: str
    rank: int = Field(description="Final rank (1 to 5)")
    why_recommended: str = Field(description="Crisp, authentic 1-2 sentence explanation of why this product is best suited for the buyer's query, context, and budget.")
    negotiation_hint: str = Field(description="Explain price status, e.g. 'Listed at ₹1500, but AI identified room to negotiate to your ₹1200 budget!' or 'Listed within budget at ₹999.'")
    is_negotiable_deal: bool = Field(description="True if listed price > budget but floor price allows negotiation, or if merchant has high flexibility.")


class ReRankOutput(BaseModel):
    ranked_results: list[ReRankedItem] = Field(description="Top 5 recommended products in order.")
    discovery_summary: str = Field(description="A brief summary for the buyer explaining the curation.")


from core.chroma_store import semantic_search


def retrieve_candidates(parsed: ParsedQuery, include_all_for_fallback: bool = False, session_id: str | None = None) -> list[dict[str, Any]]:
    """
    Step 1: AI Vector Search + SQL Candidate Retrieval
    """
    
    # Do a vector search if they have a query
    semantic_ids = []
    if parsed.translated_query or parsed.search_keywords:
        q_str = f"{parsed.translated_query} {' '.join(parsed.search_keywords)}"
        semantic_ids = semantic_search(q_str, n_results=100)
        
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        
        query_sql = """
            SELECT 
                p.id, p.merchant_id, p.product_name, p.category, 
                p.search_tags_json, p.sizes_json, p.listed_price, p.floor_price, 
                p.stock_quantity, p.image_path, p.confidence_score, 
                p.stock_last_confirmed_at,
                m.name as merchant_name, m.reliability_score as seller_rating, 
                m.merchant_dna_json
            FROM products p
            JOIN merchants m ON p.merchant_id = m.id
            WHERE p.is_prohibited = 0 AND p.stock_quantity > 0
        """
        params = []
        
        # If we got semantic matches, boost them by restricting the pool
        if semantic_ids and not include_all_for_fallback:
            placeholders = ','.join(['?']*len(semantic_ids))
            query_sql += f" AND p.id IN ({placeholders})"
            params.extend(semantic_ids)


        if session_id:
            query_sql += " AND (p.session_id IS NULL OR p.session_id = '' OR p.session_id = ? OR p.merchant_id IN ('m1', 'm2', 'm3'))"
            params.append(session_id)
        else:
            query_sql += " AND (p.session_id IS NULL OR p.session_id = '' OR p.merchant_id IN ('m1', 'm2', 'm3'))"

        if not include_all_for_fallback and parsed.max_budget is not None:
            # HIDDEN FLOOR MATCHING: Include items where listed <= budget OR floor <= budget
            query_sql += " AND (p.listed_price <= ? OR (p.floor_price IS NOT NULL AND p.floor_price <= ?))"
            params.extend([parsed.max_budget, parsed.max_budget])

        cursor.execute(query_sql, params)
        rows = cursor.fetchall()

        candidates = []
        for r in rows:
            # Update time decay confidence score
            fresh_conf = update_product_confidence(r["id"], conn=conn) or r["confidence_score"] or 100.0
            
            dna = {}
            if r["merchant_dna_json"]:
                try:
                    dna = json.loads(r["merchant_dna_json"])
                except Exception:
                    dna = {}

            tags = []
            if r["search_tags_json"]:
                try:
                    tags = json.loads(r["search_tags_json"])
                except Exception:
                    tags = []

            sizes = []
            if r["sizes_json"]:
                try:
                    sizes = json.loads(r["sizes_json"])
                except Exception:
                    sizes = []

            badge, badge_desc = get_availability_indicator(fresh_conf, r["stock_quantity"])

            candidates.append({
                "id": r["id"],
                "merchant_id": r["merchant_id"],
                "merchant_name": r["merchant_name"],
                "product_name": r["product_name"],
                "category": r["category"],
                "search_tags": tags,
                "sizes": sizes,
                "listed_price": r["listed_price"],
                "floor_price": r["floor_price"],
                "stock_quantity": r["stock_quantity"],
                "image_path": r["image_path"],
                "confidence_score": fresh_conf,
                "seller_rating": r["seller_rating"] or 4.5,
                "merchant_dna": dna,
                "availability_badge": badge,
                "availability_desc": badge_desc
            })

        return candidates
    finally:
        conn.close()


def score_candidate_heuristics(candidate: dict[str, Any], parsed: ParsedQuery) -> float:
    """
    Calculates dynamic multi-factor score combining:
    - Textual & Noun Overlap
    - Normalized Jaccard Token Similarity & Category Relevance
    - Pre-negotiation Deal Feasibility (Budget vs Listed vs Floor + Merchant Flexibility)
    - Seller Reliability (Trust)
    - Stock Confidence (Freshness)
    """
    prod_title = candidate["product_name"].lower()
    prod_text = f"{prod_title} {candidate['category']} {' '.join(candidate['search_tags'])}".lower()
    
    # 1. Keyword & Tag Match
    has_keywords = bool(parsed.search_keywords)
    kw_hits = sum(1 for kw in parsed.search_keywords if re.search(rf"\b{re.escape(kw.lower().replace('-',''))}\b", prod_text.replace('-', '')) or kw.lower() in prod_text.replace('-', ''))
    
    # Check category match (with strict gender/tier separation)
    cat_match = False
    if parsed.category and parsed.category != "General":
        parsed_parts = [p.strip().lower() for p in parsed.category.split(">")]
        cand_parts = [p.strip().lower() for p in (candidate.get("category") or "").split(">")]
        
        # Gender/Department conflict prevention
        if ("menswear" in parsed_parts and "womenswear" in cand_parts) or ("womenswear" in parsed_parts and "menswear" in cand_parts):
            cat_match = False
        elif any(p in cand_parts for p in parsed_parts if p not in ["clothing", "general", "accessories"]) or parsed_parts[0] == cand_parts[0] and not ("menswear" in parsed_parts or "womenswear" in parsed_parts):
            cat_match = True
            
    # Occasion / recipient match (e.g. saree for mom/wedding)
    occ_match = False
    if parsed.recipient_or_occasion:
        occ = parsed.recipient_or_occasion.lower()
        if occ in prod_text or (occ == "mom" and "saree" in prod_text) or (occ in ["wedding", "festive"] and "ethnic" in (candidate.get("category") or "").lower()):
            occ_match = True

    # Product noun match (words directly present in product title)
    title_tokens = set(re.findall(r'\b\w+\b', prod_title))
    noun_match = any(kw.lower() in title_tokens for kw in parsed.search_keywords if kw.lower() not in ['black', 'red', 'blue', 'green', 'white', 'pink', 'yellow', 'grey', 'cotton', 'silk'])

    if has_keywords:
        kw_score = (kw_hits / len(parsed.search_keywords))
    else:
        kw_score = 0.5 if cat_match or occ_match else 0.0

    if noun_match:
        kw_score = min(1.0, kw_score + 0.40)
    if cat_match:
        kw_score = min(1.0, kw_score + 0.25)
    elif parsed.category and parsed.category != "General" and not cat_match and not noun_match:
        kw_score = 0.0

    if occ_match:
        kw_score = min(1.0, kw_score + 0.35)

    # Color match bonus (only if product matches category or noun)
    if (cat_match or noun_match) and parsed.color:
        if parsed.color.lower() in prod_text:
            kw_score = min(1.0, kw_score + 0.25)
        else:
            # Strict Color Filter: If they explicitly asked for a color and it's not present, reject it.
            candidate["relevance"] = 0.0
            return 0.0
        
    # Size match bonus
    if (cat_match or noun_match) and parsed.preferred_sizes and any(s.upper() in [str(x).upper() for x in candidate["sizes"]] for s in parsed.preferred_sizes):
        kw_score = min(1.0, kw_score + 0.20)

    # 2. Semantic Token Overlap Similarity
    q_str = f"{parsed.translated_query} {parsed.category or ''} {' '.join(parsed.search_keywords)}".strip()
    sem_score = _compute_text_token_similarity(q_str, prod_text)

    # Vector Search already filtered candidates, so we don't need a strict lexical filter anymore.
    # Just compute relevance normally.

    if kw_score == 0.0 and sem_score == 0.0:
        # Give it a baseline semantic score since ChromaDB deemed it a match
        sem_score = 0.8

    relevance = 0.65 * kw_score + 0.35 * sem_score if sem_score > 0 else kw_score
    candidate["relevance"] = relevance

    if relevance < CONFIG.min_relevance_threshold:
        candidate["relevance"] = 0.0
        return 0.0



    # 3. Deal Feasibility ($P(\text{Deal Close})$)
    listed = candidate["listed_price"] or 1000
    floor = candidate["floor_price"] or int(listed * 0.8)
    flexibility = candidate["merchant_dna"].get("flexibility", "Flexible")
    
    deal_feasibility = 0.70
    if parsed.max_budget:
        if listed <= parsed.max_budget:
            deal_feasibility = 1.0
        elif floor <= parsed.max_budget:
            if flexibility == "Generous":
                flex_multiplier = CONFIG.generous_flexibility_multiplier
            elif flexibility == "Flexible":
                flex_multiplier = CONFIG.flexible_flexibility_multiplier
            else:
                flex_multiplier = CONFIG.firm_flexibility_multiplier

            discount_room = (listed - parsed.max_budget) / max(1, (listed - floor))
            deal_feasibility = max(0.4, 0.9 - (0.2 * discount_room)) * flex_multiplier
        else:
            deal_feasibility = 0.15

    # 4. Seller Reliability & Stock Confidence
    trust_score = min(1.0, (candidate["seller_rating"] or 4.0) / 5.0)
    freshness = min(1.0, candidate["confidence_score"] / 100.0)

    # 5. Dynamic Weight Selection based on buyer persona & intent
    if parsed.price_sensitivity == "budget_conscious":
        w = CONFIG.budget_conscious_weights
    elif parsed.price_sensitivity == "quality_first" or parsed.recipient_or_occasion in ["wedding", "diwali", "festive"]:
        w = CONFIG.quality_first_weights
    elif parsed.urgency == "urgent":
        w = CONFIG.urgent_weights
    else:
        w = CONFIG.default_weights

    composite = (w.relevance * relevance + w.deal_feasibility * deal_feasibility + w.seller_trust * trust_score + w.stock_freshness * freshness) * 100.0
    return round(composite, 2)


def llm_personal_shopper_rerank(candidates: list[dict[str, Any]], parsed: ParsedQuery) -> list[dict[str, Any]]:
    """
    Step 2: LLM Personal Shopper Re-Ranker.
    Uses Groq to contextually evaluate cultural intent, occasion, and hidden-floor negotiability.
    """
    if not candidates:
        return []

    # If only candidates and no LLM key, format directly with honest telemetry
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        top_candidates = sorted(candidates, key=lambda c: c.get("pre_score", 0), reverse=True)[:5]
        for idx, c in enumerate(top_candidates, 1):
            c["rank"] = idx
            listed = c.get("listed_price", 0)
            floor = c.get("floor_price", 0)
            if parsed.max_budget and listed > parsed.max_budget >= floor and floor > 0:
                c["is_negotiable_deal"] = True
                c["negotiation_hint"] = f"Listed at ₹{listed:,}. Negotiation agent can bid towards your ₹{parsed.max_budget:,} budget."
                c["why_recommended"] = f"Ranked #{idx} via deterministic scoring ({c.get('pre_score', 0):.1f}/100) from seller {c['merchant_name']} ({c['seller_rating']}⭐)."
            else:
                c["is_negotiable_deal"] = False
                c["negotiation_hint"] = f"Listed price: ₹{listed:,}."
                c["why_recommended"] = f"Ranked #{idx} via deterministic scoring ({c.get('pre_score', 0):.1f}/100) from seller {c['merchant_name']} ({c['seller_rating']}⭐)."
        return top_candidates

    # Select top 6 candidates by pre_score for LLM evaluation
    candidate_subset = sorted(candidates, key=lambda c: c.get("pre_score", 0), reverse=True)[:10]

    candidates_summary = []
    for c in candidate_subset:
        candidates_summary.append({
            "product_id": c["id"],
            "product_name": c["product_name"],
            "category": c["category"],
            "listed_price": c["listed_price"],
            "floor_price": c["floor_price"],
            "merchant_name": c["merchant_name"],
            "seller_rating": c["seller_rating"],
            "merchant_flexibility": c["merchant_dna"].get("flexibility", "Flexible"),
            "confidence_score": c["confidence_score"],
            "availability_badge": c["availability_badge"]
        })

    prompt = f"""
You are the expert Personal Shopper & Discovery Agent for MerchantMesh.
You are evaluating a curated shortlist of products for an Indian social commerce buyer.

BUYER CONTEXT:
- Raw Query: "{parsed.raw_query}"
- Translated Intent: "{parsed.translated_query}"
- Category: {parsed.category or 'General'}
- Max Budget: {f'₹{parsed.max_budget:,}' if parsed.max_budget else 'No strict cap'}
- Recipient / Occasion: {parsed.recipient_or_occasion or 'Not specified'}
- Price Sensitivity: {parsed.price_sensitivity}
- Urgency: {parsed.urgency}

CANDIDATE PRODUCTS FROM MERCHANTS:
{json.dumps(candidates_summary, indent=2)}

RE-RANKING INSTRUCTIONS:
1. Select the top 5 best matching items (rank 1, 2, 3, 4, 5).
2. Use human cultural intelligence (e.g. for Diwali gift for mom, evaluate traditional value; for budget queries, evaluate discount potential).
3. HIDDEN FLOOR NEGOTIATION HOOK:
   - If a product is listed above the buyer's budget but its floor_price is <= Budget, highlight that the Negotiation Agent can strike a deal! Set 'is_negotiable_deal'=True and explain this in 'negotiation_hint'.
   - STRICT CONFIDENTIALITY: NEVER disclose or reference the exact floor_price value, numerical floor amount, or the term 'floor price' in 'negotiation_hint' or 'why_recommended'. Use buyer-safe wording such as 'This item may have room for negotiation towards your budget.'
4. Explain WHY each product is recommended in crisp, authentic language in 'why_recommended'.
"""

    from core.config import invoke_structured_llm
    rerank_res = invoke_structured_llm([HumanMessage(content=prompt)], ReRankOutput, temperature=0.1, api_key=api_key)
    if rerank_res and hasattr(rerank_res, "ranked_results") and rerank_res.ranked_results:
        # Merge LLM judgments back with candidate details
        cand_map = {c["id"]: c for c in candidate_subset}
        final_ranked = []

        for item in rerank_res.ranked_results:
            if item.product_id in cand_map:
                cand = dict(cand_map[item.product_id])
                cand["rank"] = item.rank
                cand["why_recommended"] = item.why_recommended
                cand["negotiation_hint"] = item.negotiation_hint
                cand["is_negotiable_deal"] = item.is_negotiable_deal
                final_ranked.append(cand)

        if final_ranked:
            return sorted(final_ranked, key=lambda x: x["rank"])

    # Fallback to deterministic scoring
    top_candidates = sorted(candidate_subset, key=lambda c: c.get("pre_score", 0), reverse=True)[:5]
    for idx, c in enumerate(top_candidates, 1):
        c["rank"] = idx
        listed = c.get("listed_price", 0)
        floor = c.get("floor_price", 0)
        if parsed.max_budget and listed > parsed.max_budget >= floor and floor > 0:
            c["is_negotiable_deal"] = True
            c["negotiation_hint"] = f"Listed at ₹{listed:,}. Negotiation agent can bid towards your ₹{parsed.max_budget:,} budget."
            c["why_recommended"] = f"Ranked #{idx} via deterministic scoring ({c.get('pre_score', 0):.1f}/100) from seller {c['merchant_name']} ({c['seller_rating']}⭐) [LLM Degraded Mode]."
        else:
            c["is_negotiable_deal"] = False
            c["negotiation_hint"] = f"Listed price: ₹{listed:,}."
            c["why_recommended"] = f"Ranked #{idx} via deterministic scoring ({c.get('pre_score', 0):.1f}/100) from seller {c['merchant_name']} ({c['seller_rating']}⭐) [LLM Degraded Mode]."
    return top_candidates



