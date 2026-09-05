"""
Unit and Integration Tests for MerchantMesh Day 5 Trust Agent & Razorpay MCP
Verifies:
1. Code-Level Hard Price Floor Guardrail (Zero breach permitted)
2. Buyer Spending Cap & Anti-Fraud Safety Constraints
3. Human-in-the-Loop Merchant Confirmation Flow ('Y' -> 15-min Razorpay link)
4. Failure Case 1: Merchant Rejection ('N') -> Penalty + Agentic Alternative Product Discovery
5. Failure Case 2: Merchant Timeout ('TIMEOUT') -> Confidence Decay + Alternatives
6. Razorpay Webhook Handler -> Cryptographic verification + Stock auto-deduction + Seller reward
7. 15-Minute Expiry & Unpaid Payment Link Cancellation
8. Model Context Protocol (MCP) Tool Registry & Dispatch
9. Database Persistence across SQLite 'orders' and 'audit_log'
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.trust_agent import run_trust_agent
from core.razorpay_client import razorpay_client
from core.trust_engine import (
    expire_unpaid_order,
    process_payment_webhook,
    verify_spending_cap,
    verify_transaction_price_floor,
)
from data.database import get_db_connection, init_db
from mcp.razorpay_mcp_server import MCP_TOOL_REGISTRY, dispatch_mcp_call
from scripts.seed_db import seed_from_json


class TestTrustAgentAndRazorpay(unittest.TestCase):

    def setUp(self):
        init_db()
        conn = get_db_connection()
        conn.execute("DELETE FROM stock_reservations")
        conn.execute("DELETE FROM webhook_events")
        conn.execute("DELETE FROM merchant_settlements")
        conn.execute("DELETE FROM outbox_events")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM negotiations")
        conn.execute("DELETE FROM audit_log")
        conn.commit()
        conn.close()
        seed_from_json()

    def test_01_strict_code_level_floor_guardrail(self):
        """Verify code-level check strictly blocks checkout below product floor price."""
        # Product p13: Listed = 1500, Floor = 900
        passed_bad, reason_bad, details_bad = verify_transaction_price_floor(
            product_id="p13",
            proposed_price=800,
            quantity=1
        )
        self.assertFalse(passed_bad)
        self.assertIn("GUARDRAIL_VIOLATION", reason_bad)

        passed_good, reason_good, details_good = verify_transaction_price_floor(
            product_id="p13",
            proposed_price=1050,
            quantity=1
        )
        self.assertTrue(passed_good)
        self.assertEqual(reason_good, "PASSED")
        self.assertEqual(details_good["total_floor"], 900)

        # End-to-end Trust Agent execution with sub-floor price
        res = run_trust_agent(
            product_id="p13",
            agreed_price=600,
            quantity=1,
            merchant_response="Y"
        )
        self.assertEqual(res["guardrail_status"], "REJECTED_PRICE_FLOOR")
        self.assertEqual(res["status"], "GUARDRAIL_VIOLATION")
        self.assertIsNone(res["payment_link_url"])

    def test_02_buyer_spending_cap_guardrail(self):
        """Verify safety spending limits on unverified buyers."""
        passed_ok, _ = verify_spending_cap("b1", amount=5000, max_budget=8000)
        self.assertTrue(passed_ok)

        # Exceeds buyer stated budget
        passed_over_budget, reason_budget = verify_spending_cap("b1", amount=10000, max_budget=8000)
        self.assertFalse(passed_over_budget)
        self.assertIn("exceeds buyer budget cap", reason_budget)

        # Exceeds maximum informal commerce platform safety limit (₹50,000)
        passed_over_limit, reason_limit = verify_spending_cap("b1", amount=60000)
        self.assertFalse(passed_over_limit)
        self.assertIn("exceeds maximum informal commerce safety cap", reason_limit)

    def test_03_merchant_confirmation_happy_path(self):
        """
        Verify Happy Path: Guardrails pass + Merchant says 'Y'.
        Trust Agent generates Razorpay payment link with 15-min expiry.
        """
        res = run_trust_agent(
            product_id="p13",
            agreed_price=1100,
            quantity=1,
            merchant_response="Y"
        )

        self.assertEqual(res["guardrail_status"], "PASSED")
        self.assertEqual(res["status"], "PAYMENT_LINK_GENERATED")
        self.assertIsNotNone(res["payment_link_id"])
        self.assertTrue(res["payment_link_url"].startswith("http"))
        self.assertIsNotNone(res["expires_at"])
        self.assertIn("confirmed stock", res["message"])

        # Check SQLite persistence
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (res["order_id"],))
        order_row = cursor.fetchone()
        self.assertIsNotNone(order_row)
        self.assertEqual(order_row["payment_status"], "PENDING_PAYMENT")
        self.assertEqual(order_row["amount"], 1100)
        self.assertEqual(order_row["merchant_confirmed"], 1)

        # Check Audit Log
        cursor.execute("SELECT * FROM audit_log WHERE agent = 'TrustAgent' ORDER BY id DESC LIMIT 1")
        audit_row = cursor.fetchone()
        self.assertIsNotNone(audit_row)
        self.assertIn("TRUST_", audit_row["action"])
        conn.close()

    def test_04_merchant_rejection_agentic_recovery(self):
        """
        Verify Failure Case 1: Merchant says 'N' (Out of stock).
        Trust Agent applies penalty, logs rejection, and dispatches Discovery Agent to find alternatives.
        """
        res = run_trust_agent(
            product_id="p13",
            agreed_price=1200,
            quantity=1,
            merchant_response="N"
        )

        self.assertEqual(res["status"], "REJECTED_BY_MERCHANT")
        self.assertEqual(res["merchant_response"], "N")
        self.assertIsNone(res["payment_link_url"])
        self.assertIn("unavailable or out of stock", res["message"])
        
        # Verify alternative products were surfaced
        self.assertIsInstance(res["alternatives"], list)
        self.assertGreaterEqual(len(res["alternatives"]), 1)
        # Failing product itself must not be in alternatives
        for alt in res["alternatives"]:
            self.assertNotEqual(alt["id"], "p13")

        # Verify DB order record status
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE id = ?", (res["order_id"],))
        order_row = cursor.fetchone()
        self.assertIsNotNone(order_row)
        self.assertEqual(order_row["payment_status"], "REJECTED_BY_MERCHANT")
        self.assertEqual(order_row["merchant_confirmed"], 0)
        conn.close()

    def test_05_merchant_timeout_confidence_decay(self):
        """
        Verify Failure Case 2: Merchant Timeout.
        Decays confidence, penalizes merchant, and presents responsive alternative items.
        """
        res = run_trust_agent(
            product_id="p14",
            agreed_price=1000,
            quantity=1,
            merchant_response="TIMEOUT"
        )

        self.assertEqual(res["status"], "TIMEOUT_EXPIRED")
        self.assertEqual(res["merchant_response"], "TIMEOUT")
        self.assertIsNone(res["payment_link_url"])
        self.assertIn("did not respond", res["message"])
        self.assertIsInstance(res["alternatives"], list)

    def test_06_razorpay_webhook_stock_auto_deduction(self):
        """
        Verify Webhook processing automatically deducts stock in SQLite,
        updates order to PAID, and rewards merchant reliability.
        """
        # Step 1: Create an order via trust agent
        res = run_trust_agent(
            product_id="p2", # Adidas Ultraboost (listed 4000, floor 3200)
            agreed_price=6500,
            quantity=2,
            merchant_response="Y"
        )
        order_id = res["order_id"]
        plink_id = res["payment_link_id"]

        # Check initial stock
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p2'")
        initial_stock = cursor.fetchone()[0]

        cursor.execute("SELECT reliability_score FROM merchants WHERE id = 'm1'")
        initial_score = cursor.fetchone()[0]
        conn.close()

        # Step 2: Generate realistic webhook payload with cryptographic signature
        mock_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id=plink_id,
            amount_inr=6500,
            order_id=order_id,
            event="payment_link.paid"
        )

        # Step 3: Process webhook
        webhook_result = process_payment_webhook(
            raw_body=mock_event["payload_bytes"],
            signature=mock_event["signature"],
            event_id=mock_event["event_id"]
        )

        self.assertEqual(webhook_result["status"], "PAYMENT_PROCESSED_SUCCESSFULLY")
        self.assertEqual(webhook_result["payment_status"], "PAID")
        self.assertEqual(webhook_result["quantity_deducted"], 2)

        # Step 4: Verify stock auto-deduction in SQLite
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p2'")
        updated_stock = cursor.fetchone()[0]
        self.assertEqual(updated_stock, initial_stock - 2)

        # Verify order status in DB
        cursor.execute("SELECT payment_status, settlement_status FROM orders WHERE id = ?", (order_id,))
        order_db = cursor.fetchone()
        self.assertEqual(order_db["payment_status"], "PAID")
        self.assertIn(order_db["settlement_status"], ["SETTLED", "PENDING_SETTLEMENT"])

        # Verify audit log recorded webhook
        cursor.execute("SELECT * FROM audit_log WHERE action = 'PAYMENT_CONFIRMED_STOCK_DEDUCTED' ORDER BY id DESC LIMIT 1")
        audit_db = cursor.fetchone()
        self.assertIsNotNone(audit_db)
        self.assertIn(order_id, audit_db["reasoning"])
        conn.close()

    def test_07_payment_link_expiry_and_cancel(self):
        """Verify 15-minute payment link expiration & cancellation."""
        res = run_trust_agent(
            product_id="p13",
            agreed_price=1100,
            merchant_response="Y"
        )
        order_id = res["order_id"]

        exp_res = expire_unpaid_order(order_id)
        self.assertEqual(exp_res["status"], "ORDER_EXPIRED")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        status_row = cursor.fetchone()
        self.assertEqual(status_row[0], "EXPIRED")
        conn.close()

    def test_08_mcp_tool_server_registry(self):
        """Verify Model Context Protocol (MCP) tool registry and tool execution."""
        self.assertIn("create_payment_link", MCP_TOOL_REGISTRY)
        self.assertIn("check_payment_status", MCP_TOOL_REGISTRY)
        self.assertIn("cancel_payment_link", MCP_TOOL_REGISTRY)
        self.assertIn("verify_payment_signature", MCP_TOOL_REGISTRY)
        self.assertIn("refund_payment", MCP_TOOL_REGISTRY)

        # Create order in PENDING_PAYMENT state for authoritative MCP link minting
        import uuid
        unique_order_id = f"ord_mcp_test_{uuid.uuid4().hex[:8]}"
        conn = get_db_connection()
        conn.execute("""
            INSERT OR REPLACE INTO orders (
                id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status
            ) VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (unique_order_id,))
        conn.commit()
        conn.close()

        # Test MCP Tool Dispatch
        create_res = dispatch_mcp_call("create_payment_link", {
            "order_id": unique_order_id
        })
        self.assertEqual(create_res["status"], "SUCCESS")
        self.assertIsNotNone(create_res["payment_link_url"])

        # Test MCP Status Check
        status_res = dispatch_mcp_call("check_payment_status", {
            "payment_link_id": create_res["payment_link_id"]
        })
        self.assertEqual(status_res["status"], "SUCCESS")



if __name__ == "__main__":
    unittest.main()
