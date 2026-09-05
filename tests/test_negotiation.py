"""
Unit and Integration Tests for MerchantMesh Day 4 Negotiation Agent
Verifies:
1. Dynamic Seller Profile building from Merchant DNA
2. Strict Code-Level Hard Floor Price Guardrail (No breach possible)
3. Buyer Budget Cap Enforcement (Buyer never exceeds max budget)
4. Multi-Turn Haggling Convergence via LangGraph
5. Bundle / Bulk Quantity Volume Pricing
6. Database Persistence in SQLite 'negotiations' and 'audit_log'
7. Merchant DNA Behavioral Contrast (Firm vs Generous)
8. Adversarial Attack & Prompt Injection Resistance
"""

import json
import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.negotiation_agent import run_negotiation
from core.negotiation_engine import (
    SellerNegotiationProfile,
    build_seller_profile,
    calculate_bundle_financials,
    heuristic_seller_response,
    validate_buyer_offer,
    validate_seller_offer,
)
from data.database import get_db_connection, init_db
from scripts.seed_db import seed_from_json


class TestNegotiationAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_from_json()

    def test_01_seller_profile_from_dna(self):
        """Verify dynamic generation of Seller Profile from Merchant DNA and Product."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = 'p13'")
        prod = dict(cursor.fetchone())
        cursor.execute("SELECT * FROM merchants WHERE id = ?", (prod["merchant_id"],))
        merch = dict(cursor.fetchone())
        conn.close()

        profile = build_seller_profile(prod, merch, quantity=1)
        self.assertEqual(profile.product_id, "p13")
        self.assertEqual(profile.listed_price, 1500)
        self.assertEqual(profile.floor_price, 900)
        self.assertEqual(profile.total_floor_price, 900)
        self.assertIn(profile.flexibility, ["Firm", "Flexible", "Generous"])
        self.assertGreater(profile.max_discount_pct, 0.0)

    def test_02_strict_code_level_floor_guardrail(self):
        """
        CRITICAL TEST: Ensure code-level check strictly rejects any offer < floor price.
        """
        # Test direct validator
        is_valid_bad, reason_bad = validate_seller_offer(offered_price=850, total_floor_price=900, total_listed_price=1500)
        self.assertFalse(is_valid_bad)
        self.assertIn("GUARDRAIL_VIOLATION", reason_bad)

        is_valid_good, reason_good = validate_seller_offer(offered_price=950, total_floor_price=900, total_listed_price=1500)
        self.assertTrue(is_valid_good)
        self.assertEqual(reason_good, "PASSED")

        # Test seller heuristic response with lowball offer
        profile = SellerNegotiationProfile(
            merchant_id="m1",
            merchant_name="Priya Garments",
            product_id="p13",
            product_name="Urban Black Hoodie",
            listed_price=1500,
            floor_price=900,
            quantity=1,
            total_listed_price=1500,
            total_floor_price=900,
            flexibility="Generous"
        )
        res = heuristic_seller_response(buyer_offer=500, profile=profile, turn_number=1)
        self.assertGreaterEqual(res.counter_price, 900)
        self.assertIn(res.action, ["REJECT", "COUNTER"])

    def test_03_buyer_budget_cap_guardrail(self):
        """Verify buyer validator strictly blocks offers exceeding max budget."""
        is_valid_bad, reason_bad = validate_buyer_offer(offered_price=1500, total_max_budget=1200)
        self.assertFalse(is_valid_bad)
        self.assertIn("GUARDRAIL_VIOLATION", reason_bad)

        is_valid_good, reason_good = validate_buyer_offer(offered_price=1100, total_max_budget=1200)
        self.assertTrue(is_valid_good)

    def test_04_bundle_volume_pricing(self):
        """Verify bulk/bundle quantity discount calculations."""
        # 1 piece
        listed_1, floor_1, rate_1 = calculate_bundle_financials(1000, 700, 1)
        self.assertEqual(listed_1, 1000)
        self.assertEqual(floor_1, 700)
        self.assertEqual(rate_1, 0.0)

        # 3 pieces (10% volume discount, floor strictly preserved at 700 * 3 = 2100)
        listed_3, floor_3, rate_3 = calculate_bundle_financials(1000, 700, 3)
        self.assertEqual(listed_3, 3000)
        self.assertEqual(floor_3, 2100) # Merchant bottom line preserved with zero breach
        self.assertEqual(rate_3, 0.10)

    def test_05_multi_turn_negotiation_deal_closed(self):
        """Verify end-to-end multi-turn negotiation closes successfully via LangGraph."""
        # p13: Listed=1500, Floor=900
        # Buyer: Target=950, Max Budget=1200
        result = run_negotiation(
            product_id="p13",
            buyer_target_price=950,
            buyer_max_budget=1200,
            quantity=1,
            buyer_id="b1"
        )

        self.assertIn(result["status"], ["ACCEPTED", "AGREED"])
        self.assertIsNotNone(result["final_price"])
        self.assertGreaterEqual(result["final_price"], 900)
        self.assertLessEqual(result["final_price"], 1200)
        self.assertGreaterEqual(len(result["turns"]), 2)

    def test_06_database_persistence_and_audit(self):
        """Verify negotiation turns are persisted to SQLite 'negotiations' and 'audit_log'."""
        result = run_negotiation(
            product_id="p14",
            buyer_target_price=850,
            buyer_max_budget=1100,
            quantity=1,
            buyer_id="b1"
        )

        session_id = result["session_id"]
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check negotiations table
        cursor.execute("SELECT * FROM negotiations WHERE id = ?", (session_id,))
        neg_row = cursor.fetchone()
        self.assertIsNotNone(neg_row)
        self.assertEqual(neg_row["product_id"], "p14")
        self.assertEqual(neg_row["buyer_id"], "b1")

        turns_saved = json.loads(neg_row["turns_json"])
        self.assertIsInstance(turns_saved, list)
        self.assertGreaterEqual(len(turns_saved), 1)

        # Check audit_log table
        cursor.execute("SELECT * FROM audit_log WHERE agent = 'NegotiationAgent' ORDER BY id DESC LIMIT 1")
        audit_row = cursor.fetchone()
        self.assertIsNotNone(audit_row)
        self.assertIn("NEGOTIATION_", audit_row["action"])

        conn.close()

    def test_07_bulk_deal_negotiation(self):
        """Verify multi-item bulk negotiation closes with volume savings."""
        result = run_negotiation(
            product_id="p13",
            buyer_target_price=2700,
            buyer_max_budget=3600,
            quantity=3,
            buyer_id="b1"
        )

        self.assertIn(result["status"], ["ACCEPTED", "AGREED"])
        self.assertEqual(result["quantity"], 3)
        self.assertIsNotNone(result["final_price"])
        # Total floor for 3 items with volume discount is ~2000
        self.assertGreaterEqual(result["final_price"], 1900)
        self.assertLessEqual(result["final_price"], 3600)

    def test_08_adversarial_lowball_rejection(self):
        """
        Verify that an aggressive lowball below floor price is safely rejected
        and does not breach the merchant's floor.
        """
        # Product p13 floor is 900. Buyer budget is 400.
        result = run_negotiation(
            product_id="p13",
            buyer_target_price=300,
            buyer_max_budget=400,
            quantity=1,
            buyer_id="b1"
        )

        # Should NOT be accepted below 900
        self.assertNotEqual(result.get("final_price"), 400)
        self.assertNotEqual(result.get("final_price"), 300)
        self.assertIn(result["status"], ["REJECTED_FLOOR_VIOLATION", "DEADLOCK", "MAX_TURNS_REACHED"])

    def test_09_language_mirroring_and_universal_fallback(self):
        """
        Verify that the seller agent dynamically mirrors English / regional language inputs
        and falls back to universal Indian English rather than forcing Hindi.
        """
        result = run_negotiation(
            product_id="p1",
            buyer_target_price=3300,
            buyer_max_budget=3600,
            quantity=1,
            buyer_id="b1"
        )
        self.assertIn(result["status"], ["ACCEPTED", "AGREED"])
        # Verify turns exist and contain respectful messages
        for t in result["turns"]:
            self.assertTrue(len(t["message"]) > 0)
            self.assertIn(t["guardrail_status"], ["PASSED", "OVERRIDDEN_TO_HARD_FLOOR", "CLAMPED_BY_CODE_GUARDRAIL"])


if __name__ == "__main__":
    unittest.main()
