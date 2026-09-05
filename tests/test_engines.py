"""
Unit and integration tests for MerchantMesh core engines:
- Trust & Integrity Engine (Merchant DNA, confidence decay, buyer fraud checks)
- Market & Demand Intelligence Engine (search trend logging, AI price suggestions)
- Product Card Generator
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_gen import create_product_card
from core.market_intelligence import (
    get_trending_insights,
    log_buyer_search,
    suggest_price,
)
from core.trust_engine import (
    analyze_merchant_dna,
    check_buyer_trust,
    update_product_confidence,
)
from data.database import init_db
from scripts.seed_db import seed_from_json


class TestCoreEngines(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        init_db()
        seed_from_json()

    def test_merchant_dna_analysis(self):
        dna_json = analyze_merchant_dna("m1")
        self.assertIsNotNone(dna_json)
        self.assertIn("flexibility", dna_json)
        self.assertIn("price_tier", dna_json)

    def test_buyer_trust_safe(self):
        res = check_buyer_trust("b1")
        self.assertTrue(res["is_safe"])
        self.assertIsNone(res["warning"])

    def test_buyer_trust_flagged(self):
        res = check_buyer_trust("b2")
        self.assertFalse(res["is_safe"])
        self.assertIsNotNone(res["warning"])

    def test_product_confidence_decay(self):
        conf = update_product_confidence("p1")
        self.assertIsNotNone(conf)
        self.assertGreaterEqual(conf, 0.0)
        self.assertLessEqual(conf, 100.0)

    def test_market_intelligence_logging(self):
        success = log_buyer_search("test query", "TestCategory")
        self.assertTrue(success)
        trends = get_trending_insights(limit=5)
        self.assertIsInstance(trends, list)

    def test_pricing_suggestions(self):
        res = suggest_price(category="Footwear > Running Shoes", product_name="Nike Running Shoes")
        self.assertIn("suggested_listed_price", res)
        self.assertIn("message", res)

    def test_product_card_generation(self):
        os.makedirs("data/output", exist_ok=True)
        out_path = "data/output/test_unit_card.jpg"
        result = create_product_card(None, "Unit Test Product", 1999, out_path)
        self.assertIsNotNone(result)
        self.assertTrue(os.path.exists(out_path))


if __name__ == "__main__":
    unittest.main()
