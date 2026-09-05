"""
Unit and Integration Tests for MerchantMesh Day 3 Discovery Agent
Verifies:
1. Multilingual / Hinglish Query Parsing
2. Hidden-Floor Budget Matching
3. Hybrid Semantic Search & Ranking
4. Availability Indicators (✅ ⚠️ ❓) & Confidence Sync
5. Edge Cases: Budget Too Low & Zero Results
6. Trust Guardrails: Prohibited Items Exclusion
7. LangGraph Agent Workflow & SQLite Audit Trail
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.discovery_agent import run_discovery_agent
from core.discovery_engine import (
    get_availability_indicator,
    retrieve_candidates,
)
from core.query_parser import ParsedQuery, parse_buyer_query
from data.database import get_db_connection, init_db
from scripts.seed_db import seed_from_json


class TestDiscoveryAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_from_json()

    def test_01_hinglish_query_parsing(self):
        """Test Hinglish and multi-language query parsing."""
        q1 = "kala hoodie chahiye 1500 ke andar"
        res1 = parse_buyer_query(q1)
        self.assertIsInstance(res1, ParsedQuery)
        self.assertEqual(res1.max_budget, 1500)
        self.assertTrue(res1.color in ["black", "kala"] or "hoodie" in res1.search_keywords)

        q2 = "Diwali gift for mom under 3000"
        res2 = parse_buyer_query(q2)
        self.assertIsInstance(res2, ParsedQuery)
        self.assertEqual(res2.max_budget, 3000)
        self.assertTrue("mom" in (res2.recipient_or_occasion or "").lower())

    def test_02_hidden_floor_matching(self):
        """
        Verify that a product with listed_price=1500, floor_price=900 (p13)
        is successfully retrieved when buyer budget is 1200 (even though 1500 > 1200).
        """
        parsed = parse_buyer_query("black hoodie under 1200")
        candidates = retrieve_candidates(parsed)
        candidate_ids = [c["id"] for c in candidates]
        
        # p13 has listed=1500, floor=900, which is <= 1200
        # p14 has listed=1200, floor=800, which is <= 1200
        self.assertIn("p14", candidate_ids)
        self.assertIn("p13", candidate_ids)

    def test_03_availability_indicators(self):
        """Verify proper availability badging based on confidence and stock."""
        badge1, _ = get_availability_indicator(95.0, 5)
        self.assertIn("✅", badge1)

        badge2, _ = get_availability_indicator(60.0, 3)
        self.assertIn("⚠️", badge2)

        badge3, _ = get_availability_indicator(25.0, 1)
        self.assertIn("❓", badge3)

        badge4, _ = get_availability_indicator(95.0, 0)
        self.assertIn("❌", badge4)

    def test_04_budget_too_low_edge_case(self):
        """Verify graceful guidance when budget is below all available floor prices."""
        # Lowest floor price in the DB is 400 (p15 t-shirt). A budget of 150 should trigger BUDGET_TOO_LOW.
        result = run_discovery_agent("hoodie under 200")
        self.assertEqual(result["status"], "BUDGET_TOO_LOW")
        self.assertIsNotNone(result["suggested_budget"])
        self.assertGreater(result["suggested_budget"], 200)
        self.assertIn("Budget Alert", result["message"])

    def test_05_zero_results_edge_case(self):
        """Verify graceful response and trending suggestions on zero matches."""
        result = run_discovery_agent("spaceship rocket engine")
        self.assertIn(result["status"], ["NO_RESULTS", "BUDGET_TOO_LOW"])
        if result["status"] == "NO_RESULTS":
            self.assertEqual(len(result["ranked_products"]), 0)
            self.assertIn("No matching products found", result["message"])

    def test_06_prohibited_items_exclusion(self):
        """Verify that items marked is_prohibited=1 are never returned to buyers."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO products 
               (id, merchant_id, product_name, category, search_tags_json, sizes_json, listed_price, floor_price, stock_quantity, is_prohibited, confidence_score) 
               VALUES ('p_bad', 'm3', 'Illegal Switchblade Knife', 'Weapons', '["knife", "weapon"]', '[]', 500, 400, 1, 1, 100.0)"""
        )
        conn.commit()
        conn.close()

        result = run_discovery_agent("knife weapon")
        returned_ids = [p["id"] for p in result["ranked_products"]]
        self.assertNotIn("p_bad", returned_ids)

    def test_07_langgraph_pipeline_and_audit_log(self):
        """Verify end-to-end LangGraph execution and audit_log table write."""
        result = run_discovery_agent("running shoes under 3500", buyer_id="b1")
        self.assertEqual(result["status"], "SUCCESS")
        self.assertGreaterEqual(len(result["ranked_products"]), 1)
        self.assertLessEqual(len(result["ranked_products"]), 3)
        
        # Check first product structure
        top_prod = result["ranked_products"][0]
        self.assertIn("product_name", top_prod)
        self.assertIn("seller_rating", top_prod)
        self.assertIn("availability_badge", top_prod)
        self.assertIn("why_recommended", top_prod)
        self.assertIn("negotiation_hint", top_prod)

        # Check SQLite audit log entry
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM audit_log WHERE agent = 'DiscoveryAgent' ORDER BY id DESC LIMIT 1")
        audit_row = cursor.fetchone()
        self.assertIsNotNone(audit_row)
        self.assertIn("DISCOVERY_SEARCH", audit_row["action"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
