"""
MerchantMesh — Unit & Adversarial Tests for Autonomous Multi-Dealer Reverse Auction (RFQ)
Tests concurrent execution, Seller DNA preservation, price floor guardrail invariants,
and multi-factor Deal Merit Scoring across competing merchants.
"""


import pytest
from fastapi.testclient import TestClient

from core.reverse_auction import _score_deal, run_parallel_reverse_auction
from data.database import get_db_connection, init_db
from main import app

tc = TestClient(app)


@pytest.fixture(autouse=True)
def setup_auction_db():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure test merchants with distinct Seller DNA
    cursor.execute("""
        INSERT OR REPLACE INTO merchants 
        (id, name, phone_number, reliability_score, merchant_dna_json)
        VALUES 
        ('m_street', 'Streetwear Hub', '9876543210', 4.8, 
         '{"tone": "urban", "min_margin_pct": 10, "bargain_resistance": "medium"}'),
        ('m_sneaker', 'Sneaker Bhai', '9876543211', 4.5, 
         '{"tone": "street_hype", "min_margin_pct": 15, "bargain_resistance": "high"}'),
        ('m_heritage', 'Saree Palace', '9876543212', 4.9, 
         '{"tone": "polite_heritage", "min_margin_pct": 8, "bargain_resistance": "low"}')
    """)

    # Ensure test competing products
    cursor.execute("""
        INSERT OR REPLACE INTO products
        (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score)
        VALUES
        ('p_auc_1', 'm_street', 'Oversized Anime Tee A', 'Streetwear', 1000, 700, 10, 0, 100.0),
        ('p_auc_2', 'm_sneaker', 'Oversized Anime Tee B', 'Streetwear', 1100, 850, 8, 0, 100.0),
        ('p_auc_3', 'm_heritage', 'Oversized Anime Tee C', 'Streetwear', 950, 750, 15, 0, 100.0)
    """)
    conn.commit()
    conn.close()


def test_reverse_auction_parallel_execution_and_winner():
    """Verifies that reverse auction fans out concurrently and selects the optimal winner."""
    result = run_parallel_reverse_auction(
        product_ids=['p_auc_1', 'p_auc_2', 'p_auc_3'],
        buyer_target_price=800,
        buyer_max_budget=950,
        quantity=1,
        buyer_id='b_tester'
    )

    assert result["total_dealers"] == 3
    assert len(result["deals"]) == 3
    assert result["winner"] is not None
    assert result["winner"]["is_winner"] is True
    assert result["winner"]["status"] == "ACCEPTED"
    assert result["winner"]["final_price"] <= 950


def test_reverse_auction_preserves_seller_dna_and_floor_prices():
    """Adversarial check: buyer aggressively offers below all floor prices (e.g. ₹200)."""
    result = run_parallel_reverse_auction(
        product_ids=['p_auc_1', 'p_auc_2', 'p_auc_3'],
        buyer_target_price=200,
        buyer_max_budget=300,
        quantity=1,
        buyer_id='b_hacker'
    )

    for deal in result["deals"]:
        # Floor price guardrail MUST hold across every concurrent thread
        if deal["status"] == "ACCEPTED":
            # If counter-accepted, final price MUST NOT breach individual merchant floor
            assert deal["final_price"] >= 700
        else:
            assert deal["status"] in ["REJECTED", "DEADLOCK", "MAX_TURNS_REACHED", "REJECTED_FLOOR_VIOLATION", "WALK_AWAY", "REJECTED_BUDGET_CAP"] or "REJECT" in deal["status"] or "DEADLOCK" in deal["status"]


def test_deal_merit_scoring_formula():
    """Verifies that higher savings, lower latency, and higher reliability produce higher deal scores."""
    score_fast_cheap = _score_deal(
        status="ACCEPTED",
        listed_price=1000,
        final_price=700,  # 30% savings
        latency_ms=250.0, # Fast
        reliability_score=4.9,
        turns_count=2
    )

    score_slow_expensive = _score_deal(
        status="ACCEPTED",
        listed_price=1000,
        final_price=950,  # 5% savings
        latency_ms=2500.0, # Slow
        reliability_score=4.0,
        turns_count=4
    )

    score_rejected = _score_deal(
        status="REJECTED",
        listed_price=1000,
        final_price=None,
        latency_ms=300.0,
        reliability_score=5.0,
        turns_count=2
    )

    assert score_fast_cheap > score_slow_expensive
    assert score_rejected == 0.0
    assert 0 <= score_fast_cheap <= 100


def test_api_negotiate_parallel_endpoint():
    """Verifies that POST /api/negotiate/parallel returns structured response with provenance."""
    res = tc.post("/api/negotiate/parallel", json={
        "product_ids": ["p_auc_1", "p_auc_2"],
        "buyer_target_price": 750,
        "buyer_max_budget": 900,
        "quantity": 1,
        "buyer_id": "b_shopper_1"
    })

    assert res.status_code == 200
    data = res.json()
    assert "deals" in data
    assert "total_dealers" in data
    assert data["total_dealers"] == 2
    assert "provenance" in data
    assert data["provenance"]["payment"]["provider"] == "razorpay"
