"""
MerchantMesh — Guardrail Unit Tests
Proves that code-level guardrails cannot be bypassed by prompt injection,
LLM hallucination, or any external input. These are deterministic Python checks.

Run: pytest tests/test_guardrails.py -v
"""
import os
import sqlite3
import sys
from datetime import datetime, timedelta

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.negotiation_engine import validate_buyer_offer, validate_seller_offer
from core.trust_engine import (
    check_buyer_trust,
    penalize_merchant_on_failure,
    update_product_confidence,
    verify_spending_cap,
    verify_stock_availability,
    verify_transaction_price_floor,
)


# ==========================================
# Fixtures — Fresh DB for every test
# ==========================================
@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Creates a fresh isolated SQLite DB for every test case."""
    test_db = str(tmp_path / "test_merchantmesh.db")
    monkeypatch.setattr("core.config.DB_PATH", test_db)
    monkeypatch.setattr("core.trust_engine.DB_PATH", test_db)
    monkeypatch.setattr("core.negotiation_engine.DB_PATH", test_db)

    conn = sqlite3.connect(test_db)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS merchants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            phone_number TEXT DEFAULT '',
            reliability_score REAL DEFAULT 5.0,
            merchant_dna_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS buyers (
            id TEXT PRIMARY KEY,
            phone_number TEXT DEFAULT '',
            buyer_trust_score REAL DEFAULT 5.0,
            return_rate REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            merchant_id TEXT NOT NULL,
            product_name TEXT NOT NULL DEFAULT '',
            category TEXT DEFAULT '',
            search_tags_json TEXT DEFAULT '[]',
            sizes_json TEXT DEFAULT '[]',
            listed_price INTEGER DEFAULT 0,
            floor_price INTEGER DEFAULT 0,
            stock_quantity INTEGER DEFAULT 0,
            image_path TEXT DEFAULT NULL,
            is_prohibited INTEGER DEFAULT 0,
            confidence_score REAL DEFAULT 100.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            stock_last_confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS negotiations (
            id TEXT PRIMARY KEY, product_id TEXT, buyer_id TEXT, merchant_id TEXT,
            target_price INTEGER, max_budget INTEGER, outcome TEXT,
            turns_json TEXT DEFAULT '[]', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY, product_id TEXT, buyer_id TEXT, merchant_id TEXT,
            amount INTEGER, quantity INTEGER DEFAULT 1, payment_status TEXT DEFAULT 'PENDING',
            payment_link_id TEXT, negotiation_id TEXT, merchant_confirmed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS stock_reservations (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL UNIQUE,
            product_id TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity > 0),
            status TEXT NOT NULL CHECK(status IN ('ACTIVE', 'CONSUMED', 'EXPIRED')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL
        );
        CREATE TABLE IF NOT EXISTS webhook_events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED')),
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL, agent TEXT DEFAULT '', reasoning TEXT DEFAULT '',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Seed test data
    conn.execute("""INSERT INTO merchants (id, name, phone_number, reliability_score)
                    VALUES ('m1', 'Test Merchant', '+919999999999', 4.5)""")
    conn.execute("""INSERT INTO buyers (id, phone_number, buyer_trust_score, return_rate)
                    VALUES ('b1', '+918888888888', 7.0, 0.05)""")
    conn.execute("""INSERT INTO buyers (id, phone_number, buyer_trust_score, return_rate)
                    VALUES ('b_risky', '+917777777777', 2.0, 0.55)""")
    conn.execute("""INSERT INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score, stock_last_confirmed_at)
                    VALUES ('p1', 'm1', 'Black Oversized Hoodie', 'Clothing > Menswear', 1500, 900, 10, 0, 100.0, ?)""",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    conn.execute("""INSERT INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score, stock_last_confirmed_at)
                    VALUES ('p2', 'm1', 'Prohibited Weapon Replica', 'Weapons', 5000, 4000, 5, 1, 100.0, ?)""",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    conn.execute("""INSERT INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score, stock_last_confirmed_at)
                    VALUES ('p3', 'm1', 'Out of Stock Jacket', 'Clothing', 2000, 1500, 0, 0, 100.0, ?)""",
                 (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
    conn.execute("""INSERT INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score, stock_last_confirmed_at)
                    VALUES ('p_stale', 'm1', 'Stale Product', 'Clothing', 1000, 800, 5, 0, 100.0, ?)""",
                 ((datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S"),))
    conn.commit()
    conn.close()
    yield test_db


# ==========================================
# GUARDRAIL 1: Price Floor Verification
# ==========================================
class TestPriceFloorGuardrail:
    """Tests for the hard code-level price floor check.
    This guardrail runs in Python code AFTER any LLM output.
    No prompt injection or hallucination can bypass it."""

    def test_price_at_floor_passes(self):
        """Exact floor price should pass."""
        passed, msg, details = verify_transaction_price_floor("p1", 900)
        assert passed is True
        assert msg == "PASSED"

    def test_price_above_floor_passes(self):
        """Price above floor should pass."""
        passed, msg, details = verify_transaction_price_floor("p1", 1500)
        assert passed is True

    def test_price_below_floor_blocked(self):
        """Price below floor MUST be blocked — this is the critical guardrail."""
        passed, msg, details = verify_transaction_price_floor("p1", 899)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in msg
        assert "899" in msg
        assert "900" in msg

    def test_price_at_zero_blocked(self):
        """Zero price must be blocked."""
        passed, msg, details = verify_transaction_price_floor("p1", 0)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in msg

    def test_negative_price_blocked(self):
        """Negative price must be blocked."""
        passed, msg, details = verify_transaction_price_floor("p1", -500)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in msg

    def test_price_one_rupee_below_floor_blocked(self):
        """Even ₹1 below floor must be blocked — no rounding tricks."""
        passed, msg, _ = verify_transaction_price_floor("p1", 899)
        assert passed is False

    def test_nonexistent_product_blocked(self):
        """Nonexistent product ID must fail safely."""
        passed, msg, details = verify_transaction_price_floor("p_does_not_exist", 1000)
        assert passed is False
        assert "not found" in msg

    def test_bulk_discount_still_enforces_floor(self):
        """Bulk orders get volume discount but must still respect adjusted floor."""
        passed, msg, details = verify_transaction_price_floor("p1", 100, quantity=2)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in msg

    def test_bulk_order_at_adjusted_floor_passes(self):
        """Bulk order at the volume hard floor should pass."""
        # For qty=2: floor = 900 * 2 = 1800
        passed, msg, details = verify_transaction_price_floor("p1", 1800, quantity=2)
        assert passed is True

    def test_details_contain_all_fields(self):
        """Response details must include all fields for audit trail."""
        _, _, details = verify_transaction_price_floor("p1", 1000)
        assert "product_id" in details
        assert "product_name" in details
        assert "unit_floor" in details
        assert "total_floor" in details
        assert "proposed_price" in details


# ==========================================
# GUARDRAIL 2: Spending Cap
# ==========================================
class TestSpendingCapGuardrail:
    """Tests for spending cap enforcement."""

    def test_within_budget_passes(self):
        passed, msg = verify_spending_cap("b1", 1000, max_budget=2000)
        assert passed is True
        assert msg == "PASSED"

    def test_exceeds_budget_blocked(self):
        passed, msg = verify_spending_cap("b1", 3000, max_budget=2000)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in msg
        assert "budget cap" in msg.lower()

    def test_exceeds_informal_limit_blocked(self):
        """₹50,000 max for informal commerce."""
        passed, msg = verify_spending_cap("b1", 60000)
        assert passed is False
        assert "50,000" in msg

    def test_exactly_at_limit_passes(self):
        passed, msg = verify_spending_cap("b1", 50000)
        assert passed is True

    def test_zero_amount_blocked(self):
        passed, msg = verify_spending_cap("b1", 0)
        assert passed is False
        assert "non-positive" in msg.lower() or "GUARDRAIL_VIOLATION" in msg

    def test_negative_amount_blocked(self):
        passed, msg = verify_spending_cap("b1", -100)
        assert passed is False

    def test_no_budget_cap_still_enforces_safety_limit(self):
        """Even without explicit budget, ₹50K safety limit applies."""
        passed, msg = verify_spending_cap("b1", 51000)
        assert passed is False


# ==========================================
# GUARDRAIL 3: Stock Availability
# ==========================================
class TestStockGuardrail:
    """Tests for stock availability verification."""

    def test_in_stock_passes(self):
        passed, stock, msg = verify_stock_availability("p1", 1)
        assert passed is True
        assert stock == 10

    def test_out_of_stock_blocked(self):
        passed, stock, msg = verify_stock_availability("p3", 1)
        assert passed is False
        assert stock == 0

    def test_insufficient_stock_blocked(self):
        passed, stock, msg = verify_stock_availability("p1", 20)
        assert passed is False
        assert "INVENTORY_RESERVATION_VIOLATION" in msg or "Insufficient" in msg

    def test_prohibited_item_blocked(self):
        passed, stock, msg = verify_stock_availability("p2", 1)
        assert passed is False
        assert "prohibited" in msg.lower()

    def test_nonexistent_product_blocked(self):
        passed, stock, msg = verify_stock_availability("p_nonexistent", 1)
        assert passed is False

    def test_active_stock_reservation_prevents_overselling(self, fresh_db):
        """If stock is 1 and a pending payment link exists within 15 mins, a 2nd buyer must be blocked."""
        conn = sqlite3.connect(fresh_db)
        # Set stock of p1 to 1 unit
        conn.execute("UPDATE products SET stock_quantity = 1 WHERE id = 'p1'")
        # Simulate active 15-minute checkout reservation by buyer 1
        conn.execute("""
            INSERT INTO orders (id, product_id, buyer_id, merchant_id, amount, quantity, payment_status, created_at)
            VALUES ('ord_res_1', 'p1', 'b1', 'm1', 900, 1, 'PENDING_PAYMENT', datetime('now'))
        """)
        conn.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES ('res_1', 'ord_res_1', 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
        """)
        conn.commit()
        conn.close()

        # Buyer 2 tries to checkout for the same single-stock product
        passed, available, msg = verify_stock_availability("p1", 1)
        assert passed is False
        assert available == 0
        assert "INVENTORY_RESERVATION_VIOLATION" in msg


# ==========================================
# GUARDRAIL 4: Buyer Trust Assessment
# ==========================================
class TestBuyerTrustGuardrail:
    """Tests for buyer fraud detection."""

    def test_good_buyer_passes(self):
        result = check_buyer_trust("b1")
        assert result["is_safe"] is True
        assert result["warning"] is None

    def test_risky_buyer_flagged(self):
        """Buyer with >40% return rate must be flagged."""
        result = check_buyer_trust("b_risky")
        assert result["is_safe"] is False
        assert "Caution" in result["warning"]
        assert "55%" in result["warning"]

    def test_unknown_buyer_defaults_safe(self):
        """Unknown buyer treated as safe with defaults if no active hoarding."""
        result = check_buyer_trust("b_unknown")
        assert result["is_safe"] is True

    def test_sybil_denial_of_inventory_hoarding_blocked(self, fresh_db):
        """Unverified/unknown buyer attempting >=2 concurrent active holds must be blocked from locking more inventory."""
        conn = sqlite3.connect(fresh_db)
        for i in range(2):
            conn.execute(f"""
                INSERT INTO orders (id, product_id, buyer_id, merchant_id, amount, quantity, payment_status, created_at)
                VALUES ('ord_sybil_{i}', 'p1', 'b_sybil', 'm1', 900, 1, 'PENDING_PAYMENT', datetime('now'))
            """)
            conn.execute(f"""
                INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
                VALUES ('res_sybil_{i}', 'ord_sybil_{i}', 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
            """)
        conn.commit()
        conn.close()

        result = check_buyer_trust("b_sybil")
        assert result["is_safe"] is False
        assert "Anti-Hoarding Block" in result["warning"]
        assert result["active_holds"] == 2


# ==========================================
# TIME-DECAY CONFIDENCE
# ==========================================
class TestConfidenceDecay:
    """Tests for time-decay confidence scoring."""

    def test_fresh_product_high_confidence(self):
        """Product confirmed today should have ~100% confidence."""
        score = update_product_confidence("p1")
        assert score is not None
        assert score >= 95.0

    def test_stale_product_low_confidence(self):
        """Product not confirmed for 20 days should have decayed confidence."""
        score = update_product_confidence("p_stale")
        assert score is not None
        assert score < 35.0  # 100 - (20 * 3.5) = 30


# ==========================================
# MERCHANT PENALTY
# ==========================================
class TestMerchantPenalty:
    """Tests for merchant failure penalties."""

    def test_penalty_decays_confidence(self, fresh_db):
        """Penalizing a merchant should reduce product confidence by 25."""
        original = update_product_confidence("p1")
        penalize_merchant_on_failure("p1", "m1", "REJECTED")
        conn = sqlite3.connect(fresh_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT confidence_score FROM products WHERE id = 'p1'").fetchone()
        conn.close()
        assert row["confidence_score"] <= original - 24  # Allow tiny float variance


# ==========================================
# NEGOTIATION ENGINE GUARDRAILS
# ==========================================
class TestNegotiationGuardrails:
    """Tests for negotiation-level price validation."""

    def test_seller_offer_below_floor_rejected(self):
        """Seller cannot offer below their own floor price."""
        valid, reason = validate_seller_offer(
            offered_price=800,
            total_floor_price=900,
            total_listed_price=1500,
        )
        assert valid is False
        assert "floor" in reason.lower()

    def test_seller_offer_at_floor_accepted(self):
        valid, reason = validate_seller_offer(
            offered_price=900,
            total_floor_price=900,
            total_listed_price=1500,
        )
        assert valid is True

    def test_buyer_offer_above_budget_rejected(self):
        """Buyer agent must not exceed the stated max budget."""
        valid, reason = validate_buyer_offer(
            offered_price=2000,
            total_max_budget=1500,
        )
        assert valid is False

    def test_buyer_offer_within_budget_accepted(self):
        valid, reason = validate_buyer_offer(
            offered_price=1200,
            total_max_budget=1500,
        )
        assert valid is True
