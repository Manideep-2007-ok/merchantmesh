"""
MerchantMesh - Multi-Dealer Parallel Reverse Auction (RFQ) Engine
Fans out concurrent Agent-to-Agent negotiations across competing merchants,
preserving each merchant's unique Seller DNA and deterministic price floors.

Scores and selects the winning deal using a multi-factor merit formula:
Deal Score = (0.50 * Savings Score) + (0.30 * Speed Score) + (0.20 * Reliability Score)
"""

import concurrent.futures
import time
from typing import Any

from agents.negotiation_agent import run_negotiation
from data.database import get_db_connection


def _score_deal(
    status: str,
    listed_price: int,
    final_price: int | None,
    latency_ms: float,
    reliability_score: float,
    turns_count: int
) -> float:
    """
    Computes the composite Deal Merit Score (0 to 100).
    Favors high price savings, rapid response latency (speed), and merchant trust.
    """
    if status != "ACCEPTED" or not final_price or final_price <= 0:
        return 0.0

    # 1. Savings Factor (0 to 100)
    savings_amount = max(0, listed_price - final_price)
    savings_pct = (savings_amount / listed_price) * 100.0 if listed_price > 0 else 0.0
    savings_score = min(100.0, max(0.0, savings_pct * 3.5))

    # 2. Speed / Latency Factor (0 to 100)
    # Fast deals (< 800ms) get score ~85-100; slower deals decay gracefully
    speed_score = max(15.0, min(100.0, 100.0 - (latency_ms / 35.0)))

    # 3. Reliability & Trust Factor (0 to 100)
    # Scaled from merchant reliability (e.g. 4.8 * 20 = 96.0)
    reliability_norm = min(5.0, max(1.0, reliability_score))
    trust_score = (reliability_norm / 5.0) * 100.0

    # Composite Multi-Factor Score
    composite = (0.50 * savings_score) + (0.30 * speed_score) + (0.20 * trust_score)
    return round(composite, 1)


def _negotiate_single_dealer_worker(params: dict[str, Any]) -> dict[str, Any]:
    """Worker thread that executes LangGraph negotiation against a single merchant."""
    product_id = params["product_id"]
    target_price = params["target_price"]
    max_budget = params["max_budget"]
    quantity = params["quantity"]
    buyer_id = params["buyer_id"]
    session_id = params.get("session_id")
    merchant_info = params.get("merchant_info", {})
    product_info = params.get("product_info", {})

    t_start = time.time()
    try:
        res = run_negotiation(
            product_id=product_id,
            buyer_target_price=target_price,
            buyer_max_budget=max_budget,
            quantity=quantity,
            buyer_id=buyer_id,
            max_turns=4
        )
        elapsed_ms = (time.time() - t_start) * 1000.0
        status = res.get("status", "REJECTED")
        final_price = res.get("final_price")
        listed_price = (product_info.get("listed_price") or 1000) * quantity
        reliability = float(merchant_info.get("reliability_score") or 4.5)

        deal_score = _score_deal(
            status=status,
            listed_price=listed_price,
            final_price=final_price,
            latency_ms=elapsed_ms,
            reliability_score=reliability,
            turns_count=len(res.get("turns", []))
        )

        return {
            "product_id": product_id,
            "product_name": product_info.get("product_name", "Product"),
            "category": product_info.get("category", "General"),
            "image_path": product_info.get("image_path"),
            "merchant_id": merchant_info.get("id", "m1"),
            "merchant_name": merchant_info.get("name", "Merchant"),
            "merchant_dna": merchant_info.get("dna", {}),
            "reliability_score": reliability,
            "stock_quantity": product_info.get("stock_quantity", 0),
            "status": status,
            "final_price": final_price,
            "listed_price": listed_price,
            "unit_price": int(final_price / quantity) if final_price and quantity > 0 else None,
            "savings_amount": res.get("savings_amount", 0),
            "savings_pct": res.get("savings_pct", 0.0),
            "latency_ms": round(elapsed_ms, 1),
            "turns_count": len(res.get("turns", [])),
            "session_id": res.get("session_id"),
            "turns": res.get("turns", []),
            "deal_score": deal_score,
            "is_winner": False,
            "error": None
        }
    except Exception as e:
        elapsed_ms = (time.time() - t_start) * 1000.0
        return {
            "product_id": product_id,
            "product_name": product_info.get("product_name", "Product"),
            "category": product_info.get("category", "General"),
            "image_path": product_info.get("image_path"),
            "merchant_id": merchant_info.get("id", "m1"),
            "merchant_name": merchant_info.get("name", "Merchant"),
            "merchant_dna": merchant_info.get("dna", {}),
            "reliability_score": float(merchant_info.get("reliability_score") or 4.0),
            "stock_quantity": product_info.get("stock_quantity", 0),
            "status": "ERROR",
            "final_price": None,
            "listed_price": (product_info.get("listed_price") or 1000) * quantity,
            "unit_price": None,
            "savings_amount": 0,
            "savings_pct": 0.0,
            "latency_ms": round(elapsed_ms, 1),
            "turns_count": 0,
            "session_id": None,
            "turns": [],
            "deal_score": 0.0,
            "is_winner": False,
            "error": str(e)
        }


def run_parallel_reverse_auction(
    product_ids: list[str],
    buyer_target_price: int | None = None,
    buyer_max_budget: int | None = None,
    quantity: int = 1,
    buyer_id: str = "b_shopper",
    session_id: str | None = None
) -> dict[str, Any]:
    """
    Executes concurrent negotiations across competing dealers in parallel threads.
    Ranks deals by Deal Merit Score and identifies the winning merchant.
    """
    if not product_ids:
        return {"deals": [], "winner": None, "total_dealers": 0}

    # Fetch product & merchant metadata for each candidate in a single DB query
    conn = get_db_connection()
    deal_params_list = []
    try:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(product_ids))
        cursor.execute(f"""
            SELECT p.id as product_id, p.product_name, p.category, p.listed_price, p.floor_price, 
                   p.stock_quantity, p.merchant_id, p.image_path,
                   m.name as merchant_name, m.reliability_score, m.merchant_dna_json as merchant_dna
            FROM products p
            JOIN merchants m ON p.merchant_id = m.id
            WHERE p.id IN ({placeholders}) AND p.is_prohibited = 0
        """, product_ids)
        rows = cursor.fetchall()

        # Enforce category consistency: Competing dealers must offer products in the same category
        if rows:
            primary_cat = rows[0]["category"]
            same_cat_rows = [r for r in rows if r["category"] == primary_cat]
            if len(same_cat_rows) >= 2:
                rows = same_cat_rows

        # Deduplicate by merchant: keep only the cheapest product per merchant
        # This prevents the same seller appearing twice with different products
        seen_merchants = {}
        for r in rows:
            mid = r["merchant_id"]
            if mid not in seen_merchants or r["listed_price"] < seen_merchants[mid]["listed_price"]:
                seen_merchants[mid] = r
        rows = list(seen_merchants.values())

        for r in rows:
            dna = {}
            if r["merchant_dna"]:
                try:
                    import json
                    dna = json.loads(r["merchant_dna"])
                except Exception:
                    dna = {}

            deal_params_list.append({
                "product_id": r["product_id"],
                "target_price": buyer_target_price,
                "max_budget": buyer_max_budget,
                "quantity": quantity,
                "buyer_id": buyer_id,
                "session_id": session_id,
                "product_info": {
                    "product_name": r["product_name"],
                    "category": r["category"],
                    "listed_price": r["listed_price"],
                    "stock_quantity": r["stock_quantity"],
                    "image_path": r["image_path"]
                },
                "merchant_info": {
                    "id": r["merchant_id"],
                    "name": r["merchant_name"],
                    "reliability_score": r["reliability_score"],
                    "dna": dna
                }
            })
    finally:
        conn.close()

    if not deal_params_list:
        return {"deals": [], "winner": None, "total_dealers": 0}

    # Fan out concurrent negotiations in parallel
    results: list[dict[str, Any]] = []
    max_workers = min(len(deal_params_list), 6)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_negotiate_single_dealer_worker, p) for p in deal_params_list]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())

    # Sort deals by Deal Merit Score descending
    results.sort(key=lambda d: d.get("deal_score", 0.0), reverse=True)

    winner = None
    accepted_deals = [d for d in results if d.get("status") == "ACCEPTED"]
    if accepted_deals:
        accepted_deals[0]["is_winner"] = True
        winner = accepted_deals[0]
        # Mark non-winning candidate deals as OUTBID in database to prevent ghosting sellers
        non_winners = accepted_deals[1:]
        if non_winners:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                for nw in non_winners:
                    nw["status"] = "OUTBID"
                    if nw.get("session_id"):
                        cursor.execute("""
                            UPDATE negotiations 
                            SET outcome = 'OUTBID'
                            WHERE id = ? AND outcome = 'ACCEPTED'
                        """, (nw["session_id"],))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ Error updating outbid RFQ records: {e}")

    # Find fastest and cheapest for summary insight
    fastest = min(results, key=lambda d: d.get("latency_ms", 99999)) if results else None
    cheapest = min(accepted_deals, key=lambda d: d.get("final_price", 999999)) if accepted_deals else None

    return {
        "deals": results,
        "winner": winner,
        "total_dealers": len(results),
        "accepted_count": len(accepted_deals),
        "fastest_dealer": fastest.get("merchant_name") if fastest else None,
        "fastest_latency_ms": fastest.get("latency_ms") if fastest else None,
        "cheapest_dealer": cheapest.get("merchant_name") if cheapest else None,
        "cheapest_price": cheapest.get("final_price") if cheapest else None,
        "summary": (
            f"Reverse Auction completed across {len(results)} dealers in parallel. "
            f"Winner: {winner['merchant_name']} (Deal Score: {winner['deal_score']}, Price: ₹{winner['final_price']:,}, Speed: {winner['latency_ms']}ms)"
            if winner else "No dealer accepted the offer within constraints."
        )
    }
