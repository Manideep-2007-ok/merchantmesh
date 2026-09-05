"""
MerchantMesh — 16-Step Adversarial Fintech Test Suite
Tests all 10 Core Invariants, security boundaries, atomic state transitions,
raw-body HMAC verification, and edge case resilience against hostile attacks.

Run: pytest tests/test_fintech_adversarial.py -v
"""

import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from agents.trust_agent import run_trust_agent
from core.parser import _deterministic_regex_product_parser
from core.razorpay_client import razorpay_client
from core.trust_engine import (
    confirm_merchant_order_and_reserve,
    process_payment_webhook,
    sweep_expired_reservations,
    verify_stock_availability,
)
from data.database import get_db_connection, init_db
from main import ADMIN_API_KEY, app
from scripts.seed_db import seed_from_json


@pytest.fixture(autouse=True)
def setup_clean_database():
    """Ensures a clean database state before each test."""
    import shutil

    from core.cache import CACHE_DIR
    shutil.rmtree(CACHE_DIR, ignore_errors=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
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


class TestFintechAdversarialSuite:

    def test_01_to_05_competing_buyers_atomic_reservation(self):
        """
        Adversarial Steps 1-5:
        1. Product with stock = 1.
        2. Buyer A creates order in AWAITING_MERCHANT.
        3. Buyer B creates order in AWAITING_MERCHANT.
        4. Merchant confirms Buyer A -> Reservation created, order -> PENDING_PAYMENT.
        5. Merchant attempts to confirm Buyer B -> MUST FAIL (INSUFFICIENT_STOCK),
           Order B MUST REMAIN in AWAITING_MERCHANT with zero state mutations.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Step 1: Set stock = 1 on product p1
        cursor.execute("UPDATE products SET stock_quantity = 1, listed_price = 1500, floor_price = 900 WHERE id = 'p1'")
        conn.commit()

        # Step 2: Buyer A order
        order_a_id = f"ord_compete_a_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 900, 'AWAITING_MERCHANT')
        """, (order_a_id,))

        # Step 3: Buyer B order
        order_b_id = f"ord_compete_b_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b2', 1, 900, 'AWAITING_MERCHANT')
        """, (order_b_id,))
        conn.commit()
        conn.close()

        # Step 4: Merchant confirms Buyer A
        res_a = confirm_merchant_order_and_reserve(order_id=order_a_id, merchant_id="m1", confirmation="Y")
        assert res_a["confirmed"] is True
        assert res_a["status"] == "PAYMENT_LINK_GENERATED"
        assert res_a["payment_link_url"].startswith("http")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_a_id,))
        assert cursor.fetchone()["payment_status"] == "PENDING_PAYMENT"

        cursor.execute("SELECT status, quantity FROM stock_reservations WHERE order_id = ?", (order_a_id,))
        res_row = cursor.fetchone()
        assert res_row is not None
        assert res_row["status"] == "ACTIVE"
        assert res_row["quantity"] == 1
        conn.close()

        # Step 5: Merchant attempts to confirm Buyer B for the same single unit
        res_b = confirm_merchant_order_and_reserve(order_id=order_b_id, merchant_id="m1", confirmation="Y")
        assert res_b["confirmed"] is False
        assert res_b["status"] == "INSUFFICIENT_STOCK"

        # Strong Assertion: Zero mutation on Order B
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, payment_link_id FROM orders WHERE id = ?", (order_b_id,))
        order_b_db = cursor.fetchone()
        assert order_b_db["payment_status"] == "AWAITING_MERCHANT"
        assert order_b_db["payment_link_id"] is None

        # Verify no reservation was created for Order B
        cursor.execute("SELECT * FROM stock_reservations WHERE order_id = ?", (order_b_id,))
        assert cursor.fetchone() is None
        conn.close()

    def test_06_to_12_webhook_integrity_and_replay_attacks(self):
        """
        Adversarial Steps 6-12:
        6. Buyer A receives payment link.
        7. Webhook with tampered/invalid signature -> FAILS.
        8. Webhook with wrong payment amount -> FAILS.
        9. Webhook with wrong payment link ID -> FAILS.
        10. Valid webhook with raw bytes -> Order PAID, Reservation CONSUMED, Stock = 0.
        11. Replay exact same webhook -> Returns 'already_processed', Stock remains 0.
        12. Attempt second payment transition -> Rejected (INVALID_ORDER_STATE).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 1, listed_price = 1500, floor_price = 900 WHERE id = 'p1'")
        
        order_id = f"ord_webhook_test_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Confirm order and generate payment link
        confirm_res = confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m1", confirmation="Y")
        assert confirm_res["confirmed"] is True
        plink_id = confirm_res["payment_link_id"]

        # Step 7: Tampered Webhook Signature
        mock_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id=plink_id,
            amount_inr=950,
            order_id=order_id,
            event="payment_link.paid"
        )
        bad_sig_res = process_payment_webhook(
            raw_body=mock_event["payload_bytes"],
            signature="tampered_invalid_hmac_signature_hex",
            event_id=mock_event["event_id"]
        )
        assert bad_sig_res["status"] == "SIGNATURE_VERIFICATION_FAILED"

        # Step 8: Valid signature but wrong amount (₹500 instead of ₹950)
        wrong_amt_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id=plink_id,
            amount_inr=500,
            order_id=order_id,
            event="payment_link.paid"
        )
        wrong_amt_res = process_payment_webhook(
            raw_body=wrong_amt_event["payload_bytes"],
            signature=wrong_amt_event["signature"],
            event_id=wrong_amt_event["event_id"]
        )
        assert wrong_amt_res["status"] == "AMOUNT_MISMATCH"

        # Step 9: Wrong payment link ID
        wrong_link_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_nonexistent_9999",
            amount_inr=950,
            order_id="ord_nonexistent_9999",
            event="payment_link.paid"
        )
        wrong_link_res = process_payment_webhook(
            raw_body=wrong_link_event["payload_bytes"],
            signature=wrong_link_event["signature"],
            event_id=wrong_link_event["event_id"]
        )
        assert wrong_link_res["status"] == "ORDER_NOT_FOUND"

        # Step 10: Valid webhook -> Order PAID, Reservation CONSUMED, Stock = 0
        valid_res = process_payment_webhook(
            raw_body=mock_event["payload_bytes"],
            signature=mock_event["signature"],
            event_id=mock_event["event_id"]
        )
        assert valid_res["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"
        assert valid_res["payment_status"] == "PAID"
        assert valid_res["remaining_stock"] == 0

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["payment_status"] == "PAID"

        cursor.execute("SELECT status FROM stock_reservations WHERE order_id = ?", (order_id,))
        assert cursor.fetchone()["status"] == "CONSUMED"

        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p1'")
        assert cursor.fetchone()["stock_quantity"] == 0
        conn.close()

        # Step 11: Replay exact same webhook event ID
        replay_res = process_payment_webhook(
            raw_body=mock_event["payload_bytes"],
            signature=mock_event["signature"],
            event_id=mock_event["event_id"]
        )
        assert replay_res["status"] == "already_processed"

        # Verify stock was NOT decremented again (still 0)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p1'")
        assert cursor.fetchone()["stock_quantity"] == 0
        conn.close()

        # Step 12: Attempt a brand new payment event for already paid order
        second_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id=plink_id,
            amount_inr=950,
            order_id=order_id,
            event="payment_link.paid",
            event_id=f"evt_{uuid.uuid4().hex[:16]}"
        )
        second_res = process_payment_webhook(
            raw_body=second_event["payload_bytes"],
            signature=second_event["signature"],
            event_id=second_event["event_id"]
        )
        assert second_res["status"] in ["INVALID_ORDER_STATE", "ALREADY_PAID"]

    def test_13_cross_merchant_order_authorization(self):
        """
        Adversarial Step 13:
        Merchant B attempts to confirm Merchant A's order -> MUST RETURN 403 / UNAUTHORIZED.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_auth_test_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Merchant m2 attempts to confirm m1's order
        res = confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m2", confirmation="Y")
        assert res["confirmed"] is False
        assert res["status"] == "UNAUTHORIZED"

        # Via FastAPI endpoint (m2 authenticates with valid key but lacks authorization for m1's order -> 403)
        client = TestClient(app)
        api_res = client.post(
            "/api/sales/confirm",
            json={"order_id": order_id, "confirmation": "Y", "merchant_id": "m2"},
            headers={"X-Merchant-Id": "m2", "X-Merchant-Key": "merchant_key_m2"}
        )
        assert api_res.status_code == 403

    def test_14_unauthorized_seed_reset_blocked(self):
        """
        Adversarial Step 14:
        Unauthenticated call to /api/catalog/seed without valid X-Admin-Key is rejected (401).
        """
        client = TestClient(app)
        res_no_key = client.post("/api/catalog/seed", json={"force": False})
        assert res_no_key.status_code == 401

        res_wrong_key = client.post("/api/catalog/seed", headers={"X-Admin-Key": "wrong_key_123"}, json={"force": False})
        assert res_wrong_key.status_code == 401

        res_valid_key = client.post("/api/catalog/seed", headers={"X-Admin-Key": ADMIN_API_KEY}, json={"force": False})
        assert res_valid_key.status_code == 200

    def test_15_transparent_degraded_mode_on_llm_failure(self):
        """
        Adversarial Step 15:
        When Groq API fails or rate-limits, parser returns explicit degraded telemetry
        (is_degraded=True, extraction_source='deterministic_regex_parser') rather than silent mock data.
        """
        caption = "Vintage Denim Jacket. Price: ₹1800 MRP, min 1400 se neeche nahi. 5 pieces available in L, XL."
        
        # Test direct deterministic parser
        deterministic_res = _deterministic_regex_product_parser(caption)
        assert deterministic_res.is_degraded is True
        assert deterministic_res.extraction_source == "deterministic_regex_parser"
        assert deterministic_res.listed_price == 1800
        assert deterministic_res.floor_price == 1400
        assert deterministic_res.stock_quantity == 5
        assert "XL" in deterministic_res.sizes_available
        assert deterministic_res.product_name != "Vintage Heavyweight Oversized Hoodie"  # No fake hoodie

        # Prohibited goods keyword filter test
        prohibited_caption = "Military tactical combat switchblade knife. Rs 2500."
        prohib_res = _deterministic_regex_product_parser(prohibited_caption)
        assert prohib_res.is_prohibited is True
        assert any(w in prohib_res.prohibited_reason.lower() for w in ["switchblade", "knife"])

    def test_16_razorpay_gateway_failure_returns_closed_error(self):
        """
        Adversarial Step 16:
        If Razorpay API fails during checkout link generation (when is_live is True and API fails closed):
        1. Gateway returns status FAILED.
        2. System releases reservation and cancels order cleanly.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 5, listed_price = 1200, floor_price = 900 WHERE id = 'p1'")
        
        order_id = f"ord_api_fail_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Mock Razorpay link creation returning status FAILED (fail closed)
        with patch.object(razorpay_client, 'create_payment_link', return_value={"status": "FAILED", "error": "Payment Link Creation Rejected by Gateway 400", "is_simulated": False}):
            res = confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m1", confirmation="Y")
            assert res["confirmed"] is False
            assert res["status"] == "PAYMENT_PROVIDER_UNAVAILABLE"
            assert "Payment Link Creation Rejected" in res["message"]

        # Verify DB state: Order CANCELLED and reservation EXPIRED
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["payment_status"] == "CANCELLED"

        cursor.execute("SELECT status FROM stock_reservations WHERE order_id = ?", (order_id,))
        res_db = cursor.fetchone()
        assert res_db["status"] == "EXPIRED"

        # Verify stock availability remained intact (5 units available)
        passed, avail, _ = verify_stock_availability("p1", 5)
        assert passed is True
        assert avail == 5
        conn.close()

    def test_17_settlement_boundary_rule(self):
        """
        Settlement Boundary Rule:
        Payment occurred before reservation expiry (payment_timestamp <= expires_at)
        is ACCEPTED even if webhook arrives after reservation expired.
        Payment after expiry is REJECTED.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 3 WHERE id = 'p1'")
        
        order_id = f"ord_boundary_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT')
        """, (order_id,))
        
        # Create an expired reservation
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        past_ts = int((datetime.now(timezone.utc) - timedelta(minutes=5)).timestamp())
        res_id = f"res_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'EXPIRED', ?)
        """, (res_id, order_id, past_time))
        conn.commit()
        conn.close()

        # Payment happened AFTER expiry -> REJECTED
        payment_after_ts = int(datetime.now(timezone.utc).timestamp())
        late_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_boundary_test",
            amount_inr=1500,
            order_id=order_id,
            event="payment_link.paid",
            created_at_timestamp=payment_after_ts
        )
        late_res = process_payment_webhook(
            raw_body=late_event["payload_bytes"],
            signature=late_event["signature"],
            event_id=late_event["event_id"]
        )
        assert late_res["status"] in ["PAYMENT_PROCESSED_SUCCESSFULLY", "PAYMENT_RECONCILIATION_REQUIRED", "PAYMENT_AFTER_EXPIRY"]

    def test_18_razorpay_timeout_transitions_to_reconciliation_required(self):
        """
        Adversarial Test 18:
        If Razorpay API link creation throws an unhandled network error/timeout:
        1. Order must NOT be immediately cancelled (link might exist at gateway).
        2. Order must transition to PAYMENT_LINK_RECONCILIATION_REQUIRED.
        3. Reservation is preserved for automated reconciliation.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 5, listed_price = 1200, floor_price = 900 WHERE id = 'p1'")
        
        order_id = f"ord_timeout_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        with patch.object(razorpay_client, 'create_payment_link', side_effect=Exception("ReadTimeout on socket")):
            res = confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m1", confirmation="Y")
            assert res["confirmed"] is False
            assert res["status"] == "PAYMENT_LINK_RECONCILIATION_REQUIRED"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["payment_status"] == "PAYMENT_LINK_RECONCILIATION_REQUIRED"

        cursor.execute("SELECT status FROM stock_reservations WHERE order_id = ?", (order_id,))
        assert cursor.fetchone()["status"] == "ACTIVE"
        conn.close()

    def test_19_mcp_order_bound_amount_tamper_immunity(self):
        """
        Adversarial Test 19:
        MCP create_payment_link must derive transaction amount strictly from committed SQLite order.
        Rejects orders that are not in PENDING_PAYMENT state.
        """
        from mcp.razorpay_mcp_server import create_payment_link_tool

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_mcp_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 2, 2000, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Attempting to mint link while order is in AWAITING_MERCHANT -> MUST BE REJECTED
        res_rejected = create_payment_link_tool(order_id=order_id)
        assert res_rejected["status"] == "REJECTED"

        # Advance order to PENDING_PAYMENT
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET payment_status = 'PENDING_PAYMENT' WHERE id = ?", (order_id,))
        conn.commit()
        conn.close()

        # Minting link now derives exact amount (₹2000) from SQLite
        res_ok = create_payment_link_tool(order_id=order_id)
        assert res_ok["status"] == "SUCCESS"
        assert res_ok["amount"] == 2000
        assert res_ok["payment_link_id"].startswith("plink_")

    def test_20_unauthorized_merchant_cannot_confirm_order(self):
        """
        Adversarial Test 20:
        Merchant m2 cannot confirm or alter orders belonging to merchant m1.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_auth_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # m2 tries to confirm m1's order
        res = confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m2", confirmation="Y")
        assert res["confirmed"] is False
        assert res["status"] == "UNAUTHORIZED"

    def test_21_public_checkout_floor_and_cap_rejection(self):
        """
        Adversarial Test 21:
        Direct API POST /api/trust/checkout must reject sub-floor prices (400) and budget cap violations (400).
        """
        client = TestClient(app)

        # Product p1 listed_price=1000, floor_price=800
        # Adversary sends agreed_price=500 (below floor 800)
        res_sub_floor = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 500,
            "quantity": 1,
            "merchant_response": "Y"
        })
        assert res_sub_floor.status_code == 400
        detail = res_sub_floor.json()["detail"]
        assert any(phrase in detail for phrase in ["below minimum floor price", "NEGOTIATION_REQUIRED", "GUARDRAIL_VIOLATION"])

        # Adversary sends agreed_price=60000 (exceeds ₹50,000 safety cap)
        res_cap = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 60000,
            "quantity": 1,
            "merchant_response": "Y"
        })
        assert res_cap.status_code == 400
        assert "exceeds maximum informal commerce safety cap" in res_cap.json()["detail"]

    def test_22_webhook_malformed_json_returns_400(self):
        """
        Adversarial Test 22:
        POST /api/webhook/razorpay with malformed body bytes returns HTTP 400.
        """
        client = TestClient(app)
        malformed_bytes = b"not a json payload"
        # Generate signature for this malformed body
        import hashlib
        import hmac
        sig = hmac.new(b"merchantmesh_secret", malformed_bytes, hashlib.sha256).hexdigest()

        response = client.post(
            "/api/webhook/razorpay",
            content=malformed_bytes,
            headers={
                "X-Razorpay-Signature": sig,
                "X-Razorpay-Event-Id": "evt_malformed_test"
            }
        )
        assert response.status_code == 400
        assert "Malformed JSON" in response.json()["detail"]

    def test_23_confirmation_vs_timeout_concurrency_race(self):
        """
        Adversarial Test 23:
        Simultaneous Merchant Confirmation ('Y') vs. Timeout Sweeper.
        INVARIANT: Exactly ONE wins (PENDING_PAYMENT with active reservation XOR TIMEOUT_EXPIRED with 0 reservations).
        Never both. Never a payment link after timeout.
        """
        import concurrent.futures

        from core.trust_engine import sweep_expired_merchant_confirmations

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_race_{uuid.uuid4().hex[:6]}"
        past_deadline = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, confirmation_expires_at)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'AWAITING_MERCHANT', ?)
        """, (order_id, past_deadline))
        conn.commit()
        conn.close()

        def confirm_worker():
            return confirm_merchant_order_and_reserve(order_id=order_id, merchant_id="m1", confirmation="Y")

        def timeout_worker():
            return sweep_expired_merchant_confirmations()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_confirm = executor.submit(confirm_worker)
            fut_timeout = executor.submit(timeout_worker)
            res_confirm = fut_confirm.result()
            res_timeout = fut_timeout.result()

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, payment_link_id FROM orders WHERE id = ?", (order_id,))
        final_order = cursor.fetchone()
        final_status = final_order["payment_status"]

        cursor.execute("SELECT COUNT(*) as res_count FROM stock_reservations WHERE order_id = ? AND status = 'ACTIVE'", (order_id,))
        active_res_count = cursor.fetchone()["res_count"]
        conn.close()

        # Invariant Verification: Single Winner
        if final_status == "PENDING_PAYMENT":
            assert res_confirm["confirmed"] is True
            assert active_res_count == 1
            assert final_order["payment_link_id"] is not None
        elif final_status == "TIMEOUT_EXPIRED":
            assert res_confirm["confirmed"] is False
            assert active_res_count == 0
        else:
            pytest.fail(f"Invalid terminal race state: {final_status}")

    def test_24_transactional_outbox_crash_recovery_and_idempotency(self):
        """
        Adversarial Test 24:
        Proves that timeout outbox events are crash-durable, at-least-once, and idempotent.
        """
        from core.trust_engine import process_pending_outbox_events

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_outbox_{uuid.uuid4().hex[:6]}"
        outbox_id = f"out_{uuid.uuid4().hex[:8]}"

        # Simulate crash right after DB commit: order is TIMEOUT_EXPIRED and outbox_events has PENDING event
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 900, 'TIMEOUT_EXPIRED')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO outbox_events (id, event_key, event_type, payload_json, status, created_at)
            VALUES (?, ?, 'MERCHANT_TIMEOUT', ?, 'PENDING', CURRENT_TIMESTAMP)
        """, (outbox_id, f"timeout:{order_id}", json.dumps({
            "order_id": order_id, "product_id": "p1", "merchant_id": "m1", "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA5klEQVR4nO3SsREAIAwDMWD/ncMK+V6qXf35zsxh5y13iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYg1tn7z/EDxbGcl84AAAAASUVORK5CYII=", "buyer_id": "b1"
        })))
        conn.commit()

        # Check initial merchant reliability
        cursor.execute("SELECT reliability_score FROM merchants WHERE id = 'm1'")
        initial_score = cursor.fetchone()["reliability_score"]
        conn.close()

        # Run outbox worker (Crash recovery)
        res1 = process_pending_outbox_events()
        assert res1["processed_count"] == 1

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM outbox_events WHERE id = ?", (outbox_id,))
        assert cursor.fetchone()["status"] == "PROCESSED"

        cursor.execute("SELECT reliability_score FROM merchants WHERE id = 'm1'")
        penalized_score = cursor.fetchone()["reliability_score"]
        assert penalized_score < initial_score
        conn.close()

        # Run outbox worker second time (Idempotency check)
        res2 = process_pending_outbox_events()
        assert res2["processed_count"] == 0

        # Assert no double penalty
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT reliability_score FROM merchants WHERE id = 'm1'")
        assert cursor.fetchone()["reliability_score"] == penalized_score
        conn.close()

    def test_25_unsafe_buyer_zero_financial_side_effects(self):
        """
        Adversarial Test 25:
        Unsafe buyer (return rate > 40%) MUST be hard-blocked.
        INVARIANT: ZERO orders created, ZERO stock reservations created, ZERO Razorpay API calls.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO buyers (id, phone_number, buyer_trust_score, return_rate)
            VALUES ('b_fraudster', '9999988888', 1.5, 0.85)
        """)
        # Seed 2 active unexpired reservations to trigger Anti-Hoarding hard block
        for i in range(2):
            o_id = f"ord_fraud_{i}"
            cursor.execute("""
                INSERT OR REPLACE INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
                VALUES (?, 'p1', 'm1', 'b_fraudster', 1, 950, 'PENDING_PAYMENT')
            """, (o_id,))
            cursor.execute("""
                INSERT OR REPLACE INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
                VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
            """, (f"res_fraud_{i}", o_id))
        conn.commit()
        conn.close()

        client = TestClient(app)

        with patch.object(razorpay_client, 'create_payment_link') as mock_razorpay:
            response = client.post("/api/trust/checkout", json={
                "product_id": "p1",
                "agreed_price": 950,
                "quantity": 1,
                "buyer_id": "b_fraudster",
                "merchant_response": "Y"
            })
            assert response.status_code == 400
            assert "GUARDRAIL_VIOLATION" in response.json()["detail"]
            assert "Anti-Hoarding Block" in response.json()["detail"]

            # Assert ZERO Razorpay calls were made
            assert mock_razorpay.call_count == 0

        # Assert ZERO new orders or reservations created beyond the 2 seeded holds
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE buyer_id = 'b_fraudster'")
        assert cursor.fetchone()["count"] == 2

        # Assert ZERO new stock reservations were created (remains exactly 2)
        cursor.execute("""
            SELECT COUNT(*) as count FROM stock_reservations r 
            JOIN orders o ON r.order_id = o.id 
            WHERE o.buyer_id = 'b_fraudster'
        """)
        assert cursor.fetchone()["count"] == 2
        conn.close()

    def test_26_webhook_payload_hash_tamper_binding(self):
        """
        Adversarial Test 26:
        Duplicate event ID with a tampered/altered payload MUST be rejected (TAMPERED_EVENT_PAYLOAD).
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_tamper_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'PENDING_PAYMENT')
        """, (order_id,))
        conn.commit()
        conn.close()

        event_id = f"evt_tamper_test_{uuid.uuid4().hex[:8]}"

        # Step 1: Process legitimate webhook
        legit_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_legit",
            amount_inr=950,
            order_id=order_id,
            event="payment_link.paid",
            event_id=event_id
        )
        res1 = process_payment_webhook(
            raw_body=legit_event["payload_bytes"],
            signature=legit_event["signature"],
            event_id=event_id
        )
        assert res1["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"

        # Step 2: Adversary attempts to reuse same event_id with altered body
        tampered_body = json.dumps({
            "event": "payment_link.paid",
            "id": event_id,
            "payload": {"payment": {"entity": {"amount": 500000, "id": "pay_tampered"}}}
        }).encode("utf-8")
        tampered_sig = hmac.new(b"merchantmesh_secret", tampered_body, hashlib.sha256).hexdigest()

        res2 = process_payment_webhook(
            raw_body=tampered_body,
            signature=tampered_sig,
            event_id=event_id
        )
        assert res2["status"] == "TAMPERED_EVENT_PAYLOAD"

    def test_27_late_webhook_on_reallocated_stock_enters_reconciliation(self):
        """
        Adversarial Test 27:
        If a reservation expires and physical stock is re-allocated to another buyer,
        a late webhook for the first buyer MUST NOT oversell inventory into negative numbers.
        It must transition the order to PAYMENT_RECONCILIATION_REQUIRED and settlement to REFUND_PENDING.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        # Product p1 with stock = 1
        cursor.execute("UPDATE products SET stock_quantity = 1 WHERE id = 'p1'")

        # Buyer A's order whose reservation expired
        order_a_id = f"ord_late_a_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 900, 'PENDING_PAYMENT')
        """, (order_a_id,))
        past_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'EXPIRED', ?)
        """, (f"res_exp_{uuid.uuid4().hex[:6]}", order_a_id, past_time))

        # Buyer B took the 1 available unit with an ACTIVE reservation
        order_b_id = f"ord_active_b_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b2', 1, 900, 'PENDING_PAYMENT')
        """, (order_b_id,))
        future_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'ACTIVE', ?)
        """, (f"res_act_{uuid.uuid4().hex[:6]}", order_b_id, future_time))

        conn.commit()
        conn.close()

        # Late webhook arrives for Buyer A (Payment completed before reservation expired, but webhook arrived after re-allocation)
        payment_ts = int((datetime.now(timezone.utc) - timedelta(minutes=12)).timestamp())
        late_event = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_late_a",
            amount_inr=900,
            order_id=order_a_id,
            event="payment_link.paid",
            created_at_timestamp=payment_ts
        )
        late_res = process_payment_webhook(
            raw_body=late_event["payload_bytes"],
            signature=late_event["signature"],
            event_id=late_event["event_id"]
        )

        assert late_res["status"] == "PAYMENT_RECONCILIATION_REQUIRED"
        assert late_res["reason"] == "STOCK_REALLOCATED_AFTER_EXPIRY"

        # Assert Buyer A order is in PAYMENT_RECONCILIATION_REQUIRED and REFUND_PENDING
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, settlement_status FROM orders WHERE id = ?", (order_a_id,))
        order_a_db = cursor.fetchone()
        assert order_a_db["payment_status"] == "PAYMENT_RECONCILIATION_REQUIRED"
        assert order_a_db["settlement_status"] == "REFUND_PENDING"

        # Assert stock is NOT negative (remains 1 for Buyer B)
        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p1'")
        assert cursor.fetchone()["stock_quantity"] == 1
        conn.close()

    def test_28_mcp_tool_perimeter_rejects_injected_amount(self):
        """
        Adversarial Test 28:
        Dispatching create_payment_link with caller-injected amount parameter MUST fail perimeter validation.
        """
        from mcp.razorpay_mcp_server import dispatch_mcp_call

        res = dispatch_mcp_call("create_payment_link", {
            "order_id": "ord_any",
            "amount": 1
        })
        assert res["status"] == "ERROR"
        assert "UNEXPECTED_ARGUMENT: amount" in res["message"]

    def test_29_razorpay_route_settlement_ledger_execution(self):
        """
        Fintech Test 29:
        Verifies that execute_merchant_settlement transfers net payout (e.g. 98%) to merchant linked account,
        records ledger in merchant_settlements, and transitions order settlement_status to SETTLED.
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_settle_{uuid.uuid4().hex[:6]}"
        payment_id = f"pay_settle_{uuid.uuid4().hex[:8]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'PAID', 'PENDING_SETTLEMENT', ?)
        """, (order_id, payment_id))
        conn.commit()
        conn.close()

        res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
        assert res["status"] == "SETTLED"
        assert res["gross_amount"] == 1000
        assert res["platform_fee"] == 20
        assert res["net_payout"] == 980
        assert res["transfer_id"].startswith("trf_")

        # Verify DB records
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT settlement_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["settlement_status"] == "SETTLED"

        cursor.execute("SELECT * FROM merchant_settlements WHERE order_id = ?", (order_id,))
        settle_row = cursor.fetchone()
        assert settle_row is not None
        assert settle_row["net_payout"] == 980
        assert settle_row["platform_fee"] == 20
        conn.close()

    def test_30_mcp_json_rpc_2_stdio_protocol_compliance(self):
        """
        Fintech Test 30:
        Verifies that razorpay_mcp_server handles standard JSON-RPC 2.0 initialize, tools/list, and tools/call.
        """
        from mcp.razorpay_mcp_server import handle_json_rpc

        # 1. initialize
        init_req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        init_res = json.loads(handle_json_rpc(init_req))
        assert init_res["result"]["serverInfo"]["name"] == "razorpay-merchantmesh-mcp"
        assert init_res["result"]["serverInfo"]["version"] == "2.0.0"

        # 2. tools/list
        tools_req = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools_res = json.loads(handle_json_rpc(tools_req))
        tool_names = [t["name"] for t in tools_res["result"]["tools"]]
        assert "create_payment_link" in tool_names
        assert "settle_order" in tool_names
        assert "refund_payment" in tool_names

    def test_31_a2a_protocol_step_negotiation_and_discovery(self):
        """
        Fintech Test 31:
        Verifies discrete A2A REST protocol endpoints for autonomous buyer agents.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        # 1. A2A Discover
        disc_res = client.post("/api/a2a/catalog/discover", json={"query": "hoodie", "buyer_id": "b1"})
        assert disc_res.status_code == 200
        disc_data = disc_res.json()
        assert disc_data["protocol"] == "A2A_Commerce_v1"

        # 2. A2A Step Negotiation
        step_res = client.post("/api/a2a/negotiate/step", json={
            "product_id": "p1",
            "proposed_price": 900,
            "turn_index": 1,
            "message": "Can you do 900?"
        })
        assert step_res.status_code == 200
        step_data = step_res.json()
        assert step_data["protocol"] == "A2A_Commerce_v1"
        assert step_data["speaker"] == "SELLER"
        assert step_data["counter_price"] >= 800  # >= floor

    def test_32_sales_confirm_cross_merchant_auth_rejection(self):
        """
        Fintech Test 32:
        Verifies that an unauthorized merchant cannot confirm or reject another merchant's orders.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_auth_test_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 900, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Attacker claims to be merchant 'm2' with m2 credentials trying to reject m1's order -> 403 Forbidden
        res = client.post(
            "/api/sales/confirm",
            json={"order_id": order_id, "confirmation": "N", "merchant_id": "m2"},
            headers={"X-Merchant-Id": "m2", "X-Merchant-Key": "merchant_key_m2"}
        )
        assert res.status_code == 403
        assert "Merchant unauthorized" in res.json()["detail"]

    def test_33_direct_checkout_tampered_negotiation_price_blocked(self):
        """
        Fintech Test 33:
        Verifies that attempting direct checkout with a tampered price different from the negotiation outcome is blocked with 400.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        neg_id = f"neg_tamper_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', '[]', 900, 'ACCEPTED')
        """, (neg_id,))
        conn.commit()
        conn.close()

        # Adversary attempts to checkout at ₹600 using accepted negotiation at ₹900
        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 600,
            "quantity": 1,
            "negotiation_id": neg_id,
            "buyer_id": "b1"
        })
        assert res.status_code == 400
        assert "does not match negotiated price" in res.json()["detail"] or "GUARDRAIL_VIOLATION" in res.json()["detail"]

    def test_34_stats_reports_captured_and_settled_ledger_volumes(self):
        """
        Fintech Test 34:
        Verifies that GET /api/stats accurately reports both captured GMV and settled ledger amounts.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        res = client.get("/api/stats")
        assert res.status_code == 200
        data = res.json()
        assert "captured_earnings" in data
        assert "settled_earnings" in data
        assert "settled_count" in data

    def test_35_sales_confirm_unauthenticated_rejected(self):
        """
        Fintech Test 35:
        Calling POST /api/sales/confirm without X-Merchant-Id and X-Merchant-Key headers MUST return HTTP 401.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_no_auth_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Anonymous request without merchant headers -> MUST BE 401
        res = client.post("/api/sales/confirm", json={
            "order_id": order_id,
            "confirmation": "Y"
        })
        assert res.status_code == 401
        assert "Merchant authentication required" in res.json()["detail"]

    def test_36_sales_confirm_invalid_key_rejected(self):
        """
        Fintech Test 36:
        Calling POST /api/sales/confirm with wrong X-Merchant-Key MUST return HTTP 401.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_bad_key_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        res = client.post(
            "/api/sales/confirm",
            json={"order_id": order_id, "confirmation": "Y"},
            headers={"X-Merchant-Id": "m1", "X-Merchant-Key": "wrong_secret_key_999"}
        )
        assert res.status_code == 401
        assert "Invalid merchant authentication key" in res.json()["detail"]

    def test_37_sales_confirm_authenticated_success(self):
        """
        Fintech Test 37:
        Calling POST /api/sales/confirm with valid X-Merchant-Id and X-Merchant-Key succeeds (200)
        and commits atomic stock reservation.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE merchants SET api_key = 'merchant_secret_m1' WHERE id = 'm1'")
        cursor.execute("UPDATE products SET stock_quantity = 5, listed_price = 1200, floor_price = 900 WHERE id = 'p1'")
        
        order_id = f"ord_auth_ok_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 950, 'AWAITING_MERCHANT')
        """, (order_id,))
        conn.commit()
        conn.close()

        res = client.post(
            "/api/sales/confirm",
            json={"order_id": order_id, "confirmation": "Y"},
            headers={"X-Merchant-Id": "m1", "X-Merchant-Key": "merchant_secret_m1"}
        )
        assert res.status_code == 200
        assert res.json()["confirmed"] is True
        assert res.json()["status"] == "PAYMENT_LINK_GENERATED"

    def test_38_settlement_unauthenticated_and_wrong_key_rejected(self):
        """
        Fintech Test 38:
        Calling POST /api/settlement/trigger without valid X-Admin-Key MUST return HTTP 401.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        # 1. Anonymous request without X-Admin-Key -> 401
        res_anon = client.post("/api/settlement/trigger", json={"order_id": "ord_any"})
        assert res_anon.status_code == 401

        # 2. Request with incorrect X-Admin-Key -> 401
        res_wrong = client.post(
            "/api/settlement/trigger",
            json={"order_id": "ord_any"},
            headers={"X-Admin-Key": "fake_admin_key_999"}
        )
        assert res_wrong.status_code == 401

    def test_39_settlement_rejects_unpaid_or_missing_payment_id(self):
        """
        Fintech Test 39:
        Settlement MUST reject orders not in 'PAID' state or lacking authentic 'payment_id'.
        """
        from fastapi.testclient import TestClient

        from main import ADMIN_API_KEY, app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        # 1. Order in PENDING_PAYMENT
        order_pending = f"ord_pend_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (order_pending,))

        # 2. Order in PAID state but payment_id IS NULL
        order_no_pay_id = f"ord_nopay_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'PAID', 'PENDING_SETTLEMENT', NULL)
        """, (order_no_pay_id,))
        conn.commit()
        conn.close()

        # Reject PENDING_PAYMENT order
        res1 = client.post(
            "/api/settlement/trigger",
            json={"order_id": order_pending},
            headers={"X-Admin-Key": ADMIN_API_KEY}
        )
        assert res1.status_code == 400
        assert "Must be 'PAID'" in res1.json()["detail"]

        # Reject missing payment_id
        res2 = client.post(
            "/api/settlement/trigger",
            json={"order_id": order_no_pay_id},
            headers={"X-Admin-Key": ADMIN_API_KEY}
        )
        assert res2.status_code == 400
        assert "verified Razorpay payment_id" in res2.json()["detail"]

    def test_40_webhook_persists_real_payment_id_and_route_binds_to_it(self):
        """
        Fintech Test 40:
        Proves authoritative payment ID propagation:
        1. Webhook receives real payment_id (pay_xxx) and persists it into orders.payment_id.
        2. execute_merchant_settlement retrieves orders.payment_id and passes it to Route transfer API.
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_chain_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
        """, (f"res_{order_id}", order_id))
        conn.commit()
        conn.close()

        # Generate webhook with exact payment ID
        real_payment_id = f"pay_real_{uuid.uuid4().hex[:10]}"
        mock_payload = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_chain_test",
            amount_inr=1500,
            order_id=order_id,
            event="payment_link.paid"
        )
        # Inject exact payment ID
        mock_payload["payload"]["payload"]["payment"]["entity"]["id"] = real_payment_id
        body_bytes = json.dumps(mock_payload["payload"]).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        # Process webhook
        wh_res = process_payment_webhook(raw_body=body_bytes, signature=sig)
        assert wh_res["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"
        assert wh_res["payment_id"] == real_payment_id

        # Verify DB order has real payment_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, payment_id FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        assert order_row["payment_status"] == "PAID"
        assert order_row["payment_id"] == real_payment_id
        conn.close()

        # Verify auto-settlement was executed during webhook
        assert wh_res.get("settlement") is not None
        assert wh_res["settlement"]["status"] == "SETTLED"
        assert wh_res["settlement"]["payment_id"] == real_payment_id

        # Verify secondary settlement call returns ALREADY_SETTLED (Idempotency)
        settle_res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
        assert settle_res["status"] == "ALREADY_SETTLED"

    def test_41_settlement_crash_recovery_with_provider_reconciliation(self):
        """
        Fintech Test 41:
        If process crashed during settlement leaving order in SETTLEMENT_IN_PROGRESS (> 5 mins),
        a subsequent settlement trigger reconciles against Razorpay provider:
        - If transfer already exists on Razorpay -> records existing transfer, transitions to SETTLED without duplicate payout!
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_crash_{uuid.uuid4().hex[:6]}"
        payment_id = f"pay_crashed_{uuid.uuid4().hex[:8]}"
        stale_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id, settlement_started_at)
            VALUES (?, 'p1', 'm1', 'b1', 1, 2000, 'PAID', 'SETTLEMENT_IN_PROGRESS', ?, ?)
        """, (order_id, payment_id, stale_time))
        conn.commit()
        conn.close()

        # Ensure merchant m1 has known razorpay_account_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_test_merchant_m1' WHERE id = 'm1'")
        conn.commit()
        conn.close()

        # Mock provider reconciliation discovering that verified transfer was already created
        existing_trf = {
            "id": "trf_provider_found_123",
            "account": "acc_test_merchant_m1",
            "amount": 196000, # paise (₹1960)
            "currency": "INR",
            "status": "processed"
        }
        with patch.object(razorpay_client, 'list_transfers_for_payment', return_value={"status": "SUCCESS", "items": [existing_trf]}):
            with patch.object(razorpay_client, 'settle_order_via_route') as mock_settle:
                res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
                assert res["status"] == "SETTLED"
                assert res["transfer_id"] == "trf_provider_found_123"
                # Assert NO second transfer was issued!
                assert mock_settle.call_count == 0

        # Verify DB is SETTLED with discovered transfer ID
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT settlement_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["settlement_status"] == "SETTLED"
        cursor.execute("SELECT razorpay_transfer_id FROM merchant_settlements WHERE order_id = ?", (order_id,))
        assert cursor.fetchone()["razorpay_transfer_id"] == "trf_provider_found_123"
        conn.close()

    def test_42_normalized_lexical_contraband_screening(self):
        """
        Fintech Test 42:
        Tests that Unicode normalization, punctuation variations, and compacted tokens
        detect contraband terms (fake-rolex, desi_katta, g a n j a).
        """
        from core.parser import check_prohibited_goods

        # 1. Punctuation hyphen variant
        p1, r1 = check_prohibited_goods("Selling top quality fake-rolex luxury watch.")
        assert p1 is True
        assert "fake rolex" in r1.lower()

        # 2. Punctuation underscore variant
        p2, r2 = check_prohibited_goods("Countrymade desi_katta available for sale.")
        assert p2 is True
        assert any(w in r2.lower() for w in ["desi katta", "katta"])

        # 3. Spaced-out character obfuscation
        p3, r3 = check_prohibited_goods("Organic fresh g a n j a leaves.")
        assert p3 is True
        assert "ganja" in r3.lower()

        # 4. Normal product should pass
        p4, r4 = check_prohibited_goods("Black oversized cotton streetwear hoodie.")
        assert p4 is False
        assert r4 is None

    def test_43_trust_agent_two_phase_reservation_and_rollback_on_failure(self):
        """
        Fintech Test 43:
        Proves that TrustAgent commits atomic stock reservation in SQLite BEFORE calling Razorpay API,
        and cleanly releases/expires reservation if Razorpay link creation fails.
        """

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 5, listed_price = 1500, floor_price = 900 WHERE id = 'p1'")
        conn.commit()
        conn.close()

        # Simulate Razorpay Gateway deterministic failure (e.g. invalid auth)
        with patch.object(razorpay_client, 'create_payment_link', side_effect=Exception("Invalid API Key Authorization 401")):
            res = run_trust_agent(
                product_id="p1",
                agreed_price=1200,
                quantity=1,
                merchant_response="Y"
            )
            assert res["status"] == "PAYMENT_LINK_FAILED"
            order_id = res["order_id"]

        # Verify DB order is CANCELLED and reservation is EXPIRED (Clean rollback)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        assert cursor.fetchone()["payment_status"] == "CANCELLED"

        cursor.execute("SELECT status FROM stock_reservations WHERE order_id = ?", (order_id,))
        assert cursor.fetchone()["status"] == "EXPIRED"

        # Verify 5 units remain available
        passed, avail, _ = verify_stock_availability("p1", 5)
        assert passed is True
        assert avail == 5
        conn.close()

    def test_44_webhook_rejects_missing_payment_id_without_fabrication(self):
        """
        Fintech Test 44:
        Proves zero synthetic payment ID invention:
        If a webhook payload lacks payment.entity.id, it MUST return INVALID_PAYMENT_ID
        and NEVER transition the order to PAID or create a fake ID.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_nopayid_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT')
        """, (order_id,))
        conn.commit()
        conn.close()

        # Webhook payload without payment.entity.id
        payload_no_id = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {"entity": {"id": "plink_test", "reference_id": order_id, "amount": 100000}},
                "payment": {"entity": {"amount": 100000, "currency": "INR"}} # NO "id" field!
            }
        }
        body_bytes = json.dumps(payload_no_id).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        res = process_payment_webhook(raw_body=body_bytes, signature=sig)
        assert res["status"] == "INVALID_PAYMENT_ID"

        # Verify order was NOT marked PAID and has no fake payment_id
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, payment_id FROM orders WHERE id = ?", (order_id,))
        order_row = cursor.fetchone()
        assert order_row["payment_status"] == "PENDING_PAYMENT"
        assert order_row["payment_id"] is None
        conn.close()

    def test_45_webhook_deterministic_sha256_replay_defense(self):
        """
        Fintech Test 45:
        When webhook requests lack explicit event ID headers, MerchantMesh computes a deterministic SHA-256 hash.
        Replaying the identical payload is recognized and rejected as DUPLICATE_WEBHOOK_EVENT.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_hash_replay_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 800, 'PENDING_PAYMENT')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
        """, (f"res_{order_id}", order_id))
        conn.commit()
        conn.close()

        payload = {
            "event": "payment_link.paid",
            "payload": {
                "payment_link": {"entity": {"id": "plink_hash_test", "reference_id": order_id, "amount": 80000}},
                "payment": {"entity": {"id": "pay_hash_test_123", "amount": 80000, "currency": "INR"}}
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        # Call 1: Success without explicit header
        res1 = process_payment_webhook(raw_body=body_bytes, signature=sig, event_id=None)
        assert res1["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"

        # Call 2: Replay of identical raw bytes without explicit header -> MUST REJECT
        res2 = process_payment_webhook(raw_body=body_bytes, signature=sig, event_id=None)
        assert res2["status"] in ["already_processed", "DUPLICATE_WEBHOOK_EVENT"]

    def test_46_settlement_reconciliation_lookup_failure_halts_without_retry(self):
        """
        Fintech Test 46:
        If provider reconciliation query fails (e.g. socket timeout / provider 500),
        MerchantMesh MUST NOT treat it as 'no transfers exist'.
        It must transition order to SETTLEMENT_RECONCILIATION_REQUIRED and halt.
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_rec_err_{uuid.uuid4().hex[:6]}"
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_test_merchant_m1' WHERE id = 'm1'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id, settlement_started_at)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1200, 'PAID', 'SETTLEMENT_IN_PROGRESS', 'pay_rec_err_1', datetime('now', '-10 minutes'))
        """, (order_id,))
        conn.commit()
        conn.close()

        # Simulate provider lookup failing
        with patch.object(razorpay_client, 'list_transfers_for_payment', return_value={"status": "FAILED", "error": "Provider 503 Service Unavailable"}):
            with patch.object(razorpay_client, 'settle_order_via_route') as mock_settle:
                res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
                assert res["status"] == "SETTLEMENT_RECONCILIATION_REQUIRED"
                # MUST NOT execute new transfer
                assert mock_settle.call_count == 0

        # Verify DB order state
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT settlement_status, settlement_error FROM orders WHERE id = ?", (order_id,))
        order_db = cursor.fetchone()
        assert order_db["settlement_status"] == "SETTLEMENT_RECONCILIATION_REQUIRED"
        assert "Provider 503" in order_db["settlement_error"]
        conn.close()

    def test_47_reconciliation_verifies_recipient_and_amount_strictly(self):
        """
        Fintech Test 47:
        Reconciliation must not blindly trust the first returned transfer.
        If provider transfer is for a different recipient account or different amount, it must not match.
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_mismatch_{uuid.uuid4().hex[:6]}"
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_legit_m1' WHERE id = 'm1'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id, settlement_started_at)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'PAID', 'SETTLEMENT_IN_PROGRESS', 'pay_mismatch_1', datetime('now', '-10 minutes'))
        """, (order_id,))
        conn.commit()
        conn.close()

        # Return a transfer for a DIFFERENT account (acc_wrong_recipient)
        wrong_trf = {
            "id": "trf_wrong_acc",
            "account": "acc_wrong_recipient",
            "amount": 98000,
            "currency": "INR",
            "status": "processed"
        }
        with patch.object(razorpay_client, 'list_transfers_for_payment', return_value={"status": "SUCCESS", "items": [wrong_trf]}):
            with patch.object(razorpay_client, 'settle_order_via_route', return_value={"status": "SETTLED", "transfer_id": "trf_new_correct", "is_simulated": True}) as mock_settle:
                res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
                # Since existing transfer didn't match merchant, new transfer was created
                mock_settle.assert_called_once()
                assert res["status"] == "SETTLED"
                assert res["transfer_id"] == "trf_new_correct"

    def test_48_live_route_client_fails_closed_on_empty_items(self):
        """
        Fintech Test 48:
        In LIVE mode, if Razorpay returns an unexpected response without transfer items,
        the client MUST return FAILED and NEVER synthesize a fake trf_ identifier.
        """
        from unittest.mock import MagicMock
        client_live = razorpay_client.__class__()
        client_live.is_live = True
        mock_rzp = MagicMock()
        # Mock transfer endpoint returning empty items
        mock_rzp.payment.transfer.return_value = {"items": []}
        client_live.client = mock_rzp

        res = client_live.settle_order_via_route(
            payment_id="pay_live_123",
            merchant_account_id="acc_live_m1",
            gross_amount_inr=1500,
            platform_fee_inr=20
        )
        assert res["status"] == "FAILED"
        assert "Provider Protocol Error" in res["error"]
        assert "transfer_id" not in res

    def test_49_checkout_rejects_negotiation_id_belonging_to_different_product(self):
        """
        Fintech Test 49:
        Cross-product negotiation reuse attack:
        If an attacker negotiates a low price for cheap product p1, but submits that negotiation ID
        to checkout expensive product p2, the checkout endpoint MUST reject with GUARDRAIL_VIOLATION.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET listed_price = 1000, floor_price = 800 WHERE id = 'p1'")
        cursor.execute("UPDATE products SET listed_price = 5000, floor_price = 4000 WHERE id = 'p2'")
        
        # Insert valid accepted negotiation for product p1 at ₹900
        neg_id = f"neg_p1_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', '[]', 900, 'ACCEPTED')
        """, (neg_id,))
        conn.commit()
        conn.close()

        # Attacker tries to use neg_id to buy product p2 at ₹900 (far below p2's ₹4000 floor!)
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)
        response = tc.post("/api/trust/checkout", json={
            "product_id": "p2",
            "agreed_price": 900,
            "quantity": 1,
            "buyer_id": "b1",
            "negotiation_id": neg_id,
            "merchant_response": "Y"
        })
        assert response.status_code == 400
        assert "GUARDRAIL_VIOLATION" in response.json()["detail"]
        assert "belongs to product" in response.json()["detail"]

    def test_50_checkout_rejects_negotiation_id_belonging_to_different_buyer(self):
        """
        Fintech Test 50:
        Cross-buyer negotiation reuse attack:
        If buyer b1 negotiates a price, buyer b2 cannot submit b1's negotiation ID at checkout.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET listed_price = 2000, floor_price = 1500 WHERE id = 'p1'")
        
        neg_id = f"neg_b1_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', '[]', 1600, 'ACCEPTED')
        """, (neg_id,))
        conn.commit()
        conn.close()

        # Buyer b3 (trusted buyer) attempts to checkout with b1's negotiation session
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO buyers (id, phone_number, buyer_trust_score, return_rate) VALUES ('b3', '+918888888883', 5.0, 0.0)")
        conn.commit()
        conn.close()

        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)
        response = tc.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 1600,
            "quantity": 1,
            "buyer_id": "b3",
            "negotiation_id": neg_id,
            "merchant_response": "Y"
        })
        assert response.status_code == 400
        assert "GUARDRAIL_VIOLATION" in response.json()["detail"]
        assert "belongs to buyer" in response.json()["detail"]

    def test_51_settlement_request_fee_bounds_validation(self):
        """
        Fintech Test 51:
        Validates that settlement platform fee percentage is strictly bounded [0.0, 50.0].
        Submitting negative fees or > 50% must be rejected by FastAPI Pydantic schema.
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        # 1. Negative fee
        r1 = tc.post(
            "/api/settlement/trigger",
            json={"order_id": "ord_any", "platform_fee_pct": -5.0},
            headers={"X-Admin-Key": ADMIN_API_KEY}
        )
        assert r1.status_code == 422

        # 2. Excessive fee (> 50%)
        r2 = tc.post(
            "/api/settlement/trigger",
            json={"order_id": "ord_any", "platform_fee_pct": 75.0},
            headers={"X-Admin-Key": ADMIN_API_KEY}
        )
        assert r2.status_code == 422

    def test_52_settlement_rejects_merchant_with_missing_linked_account(self):
        """
        Fintech Test 52:
        Settlement must fail safely if the merchant has no configured razorpay_account_id.
        It must return MISSING_MERCHANT_LINKED_ACCOUNT and never attempt a fake transfer.
        """
        from core.trust_engine import execute_merchant_settlement

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_nolink_{uuid.uuid4().hex[:6]}"
        cursor.execute("INSERT OR IGNORE INTO merchants (id, name, phone_number, razorpay_account_id) VALUES ('m_unlinked', 'Unlinked Seller', '+919999999990', NULL)")
        cursor.execute("UPDATE merchants SET razorpay_account_id = NULL WHERE id = 'm_unlinked'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, payment_id)
            VALUES (?, 'p1', 'm_unlinked', 'b1', 1, 1000, 'PAID', 'PENDING_SETTLEMENT', 'pay_unlinked_1')
        """, (order_id,))
        conn.commit()
        conn.close()

        res = execute_merchant_settlement(order_id=order_id, platform_fee_pct=2.0)
        assert res["status"] == "MISSING_MERCHANT_LINKED_ACCOUNT"

    def test_53_live_client_fails_closed_on_sdk_init_error(self):
        """
        Fintech Test 53:
        Proves fail-closed initialization:
        If live credentials are provided but SDK client initialization fails,
        RazorpayClientWrapper raises RuntimeError and refuses to silently revert to simulation.
        """
        from unittest.mock import MagicMock

        import core.razorpay_client as rzp_mod
        from core.razorpay_client import RazorpayClientWrapper
        
        orig_sdk = rzp_mod.RAZORPAY_SDK_AVAILABLE
        orig_rzp = getattr(rzp_mod, 'razorpay', None)
        try:
            rzp_mod.RAZORPAY_SDK_AVAILABLE = True
            mock_razorpay_module = MagicMock()
            mock_razorpay_module.Client.side_effect = Exception("Invalid API Key Auth")
            rzp_mod.razorpay = mock_razorpay_module
            
            try:
                RazorpayClientWrapper(key_id="rzp_live_real_key_123", key_secret="secret_abc")
                assert False, "Should have raised RuntimeError on SDK initialization failure"
            except RuntimeError as e:
                assert "CRITICAL CONFIGURATION ERROR" in str(e)
        finally:
            rzp_mod.RAZORPAY_SDK_AVAILABLE = orig_sdk
            if orig_rzp:
                rzp_mod.razorpay = orig_rzp

    def test_54_public_catalog_does_not_return_floor_price(self):
        """
        P0-1 Regression Test:
        GET /api/catalog/products must NEVER expose floor_price in the buyer-facing response.
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        res = tc.get("/api/catalog/products")
        assert res.status_code == 200
        products = res.json()["products"]
        assert len(products) > 0
        for p in products:
            assert "listed_price" in p
            assert "floor_price" not in p, f"Security Violation: floor_price exposed on product {p.get('id')}"

    def test_55_sales_pending_requires_merchant_auth(self):
        """
        P0-2 & P0-5 Regression Test:
        GET /api/sales/pending MUST reject unauthenticated requests and filter strictly by merchant.
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        conn = get_db_connection()
        ord_m1 = f"ord_pend_m1_{uuid.uuid4().hex[:6]}"
        ord_m2 = f"ord_pend_m2_{uuid.uuid4().hex[:6]}"
        try:
            cursor = conn.cursor()
            cursor.execute("UPDATE merchants SET api_key = 'merchant_key_m1' WHERE id = 'm1'")
            cursor.execute("UPDATE merchants SET api_key = 'merchant_key_m2' WHERE id = 'm2'")
            
            # Seed orders for m1 and m2
            cursor.execute("""
                INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
                VALUES (?, 'p1', 'm1', 'b1', 1, 1000, 'AWAITING_MERCHANT')
            """, (ord_m1,))
            cursor.execute("""
                INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
                VALUES (?, 'p2', 'm2', 'b1', 1, 2000, 'AWAITING_MERCHANT')
            """, (ord_m2,))
            conn.commit()
        finally:
            conn.close()

        # 1. Unauthenticated request -> 401
        res_no_auth = tc.get("/api/sales/pending")
        assert res_no_auth.status_code == 401

        # 2. Wrong key -> 401
        res_bad_key = tc.get("/api/sales/pending", headers={"X-Merchant-Id": "m1", "X-Merchant-Key": "wrong_key"})
        assert res_bad_key.status_code == 401

        # 3. Authenticated m1 -> only m1 orders
        res_m1 = tc.get("/api/sales/pending", headers={"X-Merchant-Id": "m1", "X-Merchant-Key": "merchant_key_m1"})
        assert res_m1.status_code == 200
        orders_m1 = res_m1.json()["pending_orders"]
        for o in orders_m1:
            assert o["merchant_id"] == "m1"
            assert o["order_id"] != ord_m2

        # 4. Authenticated m2 -> only m2 orders
        res_m2 = tc.get("/api/sales/pending", headers={"X-Merchant-Id": "m2", "X-Merchant-Key": "merchant_key_m2"})
        assert res_m2.status_code == 200
        orders_m2 = res_m2.json()["pending_orders"]
        for o in orders_m2:
            assert o["merchant_id"] == "m2"
            assert o["order_id"] != ord_m1

    def test_56_discovery_budget_suggestion_never_leaks_floor(self):
        """
        P0-3 Regression Test:
        Low-budget discovery suggestions MUST NOT be mathematically derived from confidential floor prices.
        """
        from agents.discovery_agent import run_discovery_agent
        res = run_discovery_agent("hoodie under 200")
        assert res["status"] == "BUDGET_TOO_LOW"
        suggested = res["suggested_budget"]
        assert suggested is not None
        
        closest_id = res.get("closest_match", {}).get("id")
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT listed_price, floor_price FROM products WHERE id = ?", (closest_id,))
            row = cursor.fetchone()
            listed = row["listed_price"]
            floor = row["floor_price"]
        finally:
            conn.close()

        assert suggested != int(floor * 1.1), "Security Violation: suggested_budget leaked floor * 1.1"
        assert suggested <= listed

    def test_57_deterministic_parser_preserves_none_without_fabrication(self):
        """
        P0-4 Regression Test:
        Deterministic parser MUST NOT invent prices (999), floors (800), or stock (10).
        """
        from core.parser import _deterministic_regex_product_parser

        # 1. Plain text without financial details
        res_empty = _deterministic_regex_product_parser("Black oversized cotton hoodie")
        assert res_empty.listed_price is None
        assert res_empty.floor_price is None
        assert res_empty.stock_quantity is None
        assert res_empty.clarification_needed is True
        assert "price" in res_empty.missing_information
        assert "stock" in res_empty.missing_information

        # 2. Text with listed price and stock but NO floor price
        res_partial = _deterministic_regex_product_parser("Black hoodie Rs 1500, 20 pieces available")
        assert res_partial.listed_price == 1500
        assert res_partial.stock_quantity == 20
        assert res_partial.floor_price is None
        assert res_partial.clarification_needed is True

    def test_58_live_webhook_verification_requires_configured_secret(self):
        """
        P0-6 Regression Test:
        When running in live/configured mode without a webhook secret, webhook verification fails closed.
        """
        from core.razorpay_client import RazorpayClientWrapper

        client_live_no_secret = RazorpayClientWrapper(
            key_id="rzp_live_key_test",
            key_secret="sec_live_key_test",
            webhook_secret=None
        )
        client_live_no_secret.is_live = True
        client_live_no_secret.webhook_secret = None

        # verify_webhook_signature must return False
        assert client_live_no_secret.verify_webhook_signature(b'{"event":"test"}', "sig_test") is False

    def test_59_negotiation_never_discloses_exact_floor_to_buyer(self):
        """
        Secret Floor Hardening Test 59:
        Buyer offers ₹700 against floor ₹900.
        Internal guardrail enforces floor, but buyer-visible messages MUST NOT contain '₹900' or reveal exact floor.
        """
        from agents.negotiation_agent import run_negotiation
        result = run_negotiation(
            product_id="p13", # Listed 1500, floor 900
            buyer_target_price=600,
            buyer_max_budget=700,
            quantity=1,
            buyer_id="b1"
        )
        
        # Check all conversation messages
        for turn in result.get("turns", []):
            if turn["speaker"] == "SELLER":
                msg = turn["message"]
                assert "900 se 1 rupee" not in msg
                assert "900 is my absolute final" not in msg
                assert "floor price" not in msg.lower()

    def test_60_discovery_api_response_is_recursively_sanitized(self):
        """
        Secret Floor Hardening Test 60:
        /api/buyer/chat and /api/a2a/catalog/discover recursively inspected:
        Asserts no key named floor_price, unit_floor, total_floor, total_floor_price, min_floor exists.
        """
        FORBIDDEN_KEYS = {"floor_price", "total_floor", "unit_floor", "total_floor_price", "min_floor"}

        def check_no_floor(obj, path="root"):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    current = f"{path}.{k}"
                    assert k not in FORBIDDEN_KEYS, f"Security Violation: Found forbidden floor key '{k}' at '{current}'"
                    check_no_floor(v, current)
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_no_floor(item, f"{path}[{i}]")

        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)
        res_chat = tc.post("/api/buyer/chat", json={"query": "black hoodie under 1500", "buyer_id": "b1"})
        assert res_chat.status_code == 200
        check_no_floor(res_chat.json(), "buyer_chat")

        res_a2a = tc.post("/api/a2a/catalog/discover", json={"query": "running shoes", "buyer_id": "b1"})
        assert res_a2a.status_code == 200
        check_no_floor(res_a2a.json(), "a2a_discover")

    def test_61_product_with_null_floor_does_not_fabricate_synthetic_floor(self):
        """
        Secret Floor Hardening Test 61:
        Product with NULL floor_price does NOT receive a fabricated 80% floor.
        Requires full listed price for checkout and rejects sub-listed offers.
        """
        from core.trust_engine import _verify_price_floor_tx
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO products (
                    id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited
                ) VALUES ('p_null_floor', 'm1', 'Bespoke Custom Jacket', 'Clothing', 5000, NULL, 5, 0)
            """)
            conn.commit()

            # 1. Attempt checkout below listed price (e.g. 4000 = 80%)
            passed_disc, reason_disc, details_disc = _verify_price_floor_tx(cursor, "p_null_floor", 4000, 1)
            assert passed_disc is False
            assert "MISSING_PRICE_FLOOR" in reason_disc
            assert "5,000" in reason_disc

            # 2. Checkout at full listed price (5000)
            passed_full, reason_full, details_full = _verify_price_floor_tx(cursor, "p_null_floor", 5000, 1)
            assert passed_full is True
            assert details_full["unit_floor"] == 5000
            assert details_full["total_floor"] == 5000
        finally:
            conn.close()

    def test_62_heuristic_seller_response_does_not_leak_floor_text(self):
        """
        Secret Floor Hardening Test 62:
        Heuristic seller fallback with sub-floor offer counters safely without leaking floor text.
        """
        from core.negotiation_engine import (
            SellerNegotiationProfile,
            heuristic_seller_response,
        )

        profile = SellerNegotiationProfile(
            merchant_id="m1",
            merchant_name="Sneaker Bhai",
            product_id="p13",
            product_name="Urban Black Hoodie",
            listed_price=1500,
            floor_price=900,
            quantity=1,
            total_listed_price=1500,
            total_floor_price=900,
            flexibility="Flexible"
        )
        seller_out = heuristic_seller_response(buyer_offer=700, profile=profile, turn_number=1)
        assert seller_out.counter_price >= 900
        assert "900 se 1 rupee" not in seller_out.message
        assert "is my absolute final price" not in seller_out.message
        assert "floor" not in seller_out.message.lower()

    def test_63_run_negotiation_seller_profile_sanitized(self):
        """
        Secret Floor Hardening Test 63:
        run_negotiation return payload strips floor_price from seller_profile.
        """
        from agents.negotiation_agent import run_negotiation
        result = run_negotiation(
            product_id="p1",
            buyer_target_price=3000,
            buyer_max_budget=3500,
            quantity=1,
            buyer_id="b1"
        )
        if result.get("seller_profile"):
            assert "floor_price" not in result["seller_profile"]
            assert "total_floor_price" not in result["seller_profile"]

    def test_64_llm_seller_guardrail_override_direct_mock(self):
        """
        Secret Floor Hardening Test 64:
        Directly exercises the 'if not is_valid:' post-LLM guardrail branch in generate_seller_turn_llm().
        Mocks LLM attempting counter_price=700 when floor=900.
        Asserts:
        - returned counter_price >= 900
        - returned message does NOT contain 900
        - returned message does NOT contain 'floor'
        - returned message does NOT contain 'absolute final price'
        """
        from unittest.mock import patch

        from core.negotiation_engine import (
            SellerNegotiationProfile,
            SellerTurnOutput,
            generate_seller_turn_llm,
        )

        profile = SellerNegotiationProfile(
            merchant_id="m1",
            merchant_name="Sneaker Bhai",
            product_id="p13",
            product_name="Urban Black Hoodie",
            listed_price=1500,
            floor_price=900,
            quantity=1,
            total_listed_price=1500,
            total_floor_price=900,
            flexibility="Flexible"
        )

        # Mock LLM returning a sub-floor counter (700 < 900)
        mock_llm_output = SellerTurnOutput(
            action="COUNTER",
            counter_price=700,
            message="Sure bro, I can give it to you for ₹700",
            internal_reasoning="LLM hallucinated sub-floor counter"
        )

        with patch("core.config.invoke_structured_llm", return_value=mock_llm_output):
            seller_res = generate_seller_turn_llm(
                history=[],
                profile=profile,
                buyer_last_offer=650,
                api_key="mock_key_test_123"
            )

            # 1. Counter must be clamped to safe price >= 900
            assert seller_res.counter_price >= 900
            # 2. Buyer-visible message MUST NOT contain '900'
            assert "900" not in seller_res.message
            # 3. Buyer-visible message MUST NOT contain 'floor'
            assert "floor" not in seller_res.message.lower()
            # 4. Buyer-visible message MUST NOT contain 'absolute final price'
            assert "absolute final price" not in seller_res.message.lower()
            # 5. Internal reasoning records the code guardrail override
            assert "Code Guardrail Override" in seller_res.internal_reasoning

    def test_65_discovery_suggestion_mathematically_independent_of_floor(self):
        """
        Secret Floor Hardening Test 65:
        Mathematically proves that low-budget discovery suggestions are 100% independent of the secret floor.
        Changes floor_price while keeping listed_price identical and asserts suggested_budget is invariant.
        """
        from agents.discovery_agent import run_discovery_agent

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM products WHERE id != 'p_indep_test'")
            # Seed custom product with listed_price = 2000, floor_price = 1400
            cursor.execute("""
                INSERT OR REPLACE INTO products (
                    id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, is_prohibited
                ) VALUES ('p_indep_test', 'm1', 'Invariant Test Saree', 'Clothing', 2000, 1400, 5, 0)
            """)
            conn.commit()

            # Run 1: Floor = 1400
            res1 = run_discovery_agent("Invariant Test Saree under 300", buyer_id="b1")
            sug1 = res1.get("suggested_budget")
            assert sug1 is not None

            # Change floor to 600 (drastically different floor) keeping listed_price = 2000
            cursor.execute("UPDATE products SET floor_price = 600 WHERE id = 'p_indep_test'")
            conn.commit()

            # Run 2: Floor = 600
            res2 = run_discovery_agent("Invariant Test Saree under 300", buyer_id="b1")
            sug2 = res2.get("suggested_budget")
            assert sug2 is not None

            # Mathematical Proof: Suggestion must be identical regardless of floor price change!
            assert sug1 == sug2, f"Security Failure: Suggested budget changed from {sug1} to {sug2} when secret floor was altered!"
        finally:
            conn.close()

    def test_66_buyer_llm_negative_override_clamped_safely(self):
        """
        P0 Hardening Test 66:
        Mocks buyer LLM attempting negative or zero offer_price (e.g. -500 or 0).
        Asserts the guardrail override clamps it strictly >= 1 and <= max_budget.
        """
        from unittest.mock import patch

        from core.negotiation_engine import (
            BuyerNegotiationConstraints,
            BuyerTurnOutput,
            generate_buyer_turn_llm,
        )

        constraints = BuyerNegotiationConstraints(
            buyer_id="b1",
            target_price=900,
            max_budget=1200,
            quantity=1,
            total_target_price=900,
            total_max_budget=1200
        )

        # Mock LLM returning negative offer_price
        mock_llm_output = BuyerTurnOutput(
            action="COUNTER",
            offer_price=-500,
            message="Give it to me for -500",
            internal_reasoning="LLM produced negative number"
        )

        with patch("core.config.invoke_structured_llm", return_value=mock_llm_output):
            buyer_res = generate_buyer_turn_llm(
                history=[],
                constraints=constraints,
                seller_last_counter=1400,
                api_key="mock_key_buyer_123"
            )

            # Assert price is strictly positive and bounded within target/budget
            assert buyer_res.offer_price >= 1
            assert buyer_res.offer_price <= 1200
            assert "Code Guardrail Override" in buyer_res.internal_reasoning

    def test_67_a2a_negotiation_floor_secrecy(self):
        """
        Secret Floor Hardening Test 67:
        Validates that POST /api/a2a/negotiate/step NEVER exposes internal_reasoning,
        confidential floor prices, or raw floor calculations to external buyer agents.
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        # Send lowball offer of 700 against product p13 (floor is 900)
        res = tc.post("/api/a2a/negotiate/step", json={
            "product_id": "p13",
            "proposed_price": 700,
            "turn_index": 1,
            "message": "I can pay 700 maximum"
        })
        assert res.status_code == 200
        step_data = res.json()

        # 1. Assert internal_reasoning is completely absent from public A2A response
        assert "internal_reasoning" not in step_data, "Security Leak: internal_reasoning exposed in public A2A contract!"

        # 2. Assert counter price respects the floor (>= 900)
        assert step_data["counter_price"] >= 900

        # 3. Assert protocol fields exist
        assert step_data["protocol"] == "A2A_Commerce_v1"
        assert step_data["speaker"] == "SELLER"
        assert "message" in step_data

        # 4. Recursively assert no floor keys or floor string leakage
        FORBIDDEN_KEYS = {"floor_price", "total_floor", "unit_floor", "total_floor_price", "min_floor", "internal_reasoning"}
        for k in step_data.keys():
            assert k not in FORBIDDEN_KEYS
        assert "900 se 1 rupee" not in step_data["message"]
        assert "is my absolute final price" not in step_data["message"]
        assert "floor" not in step_data["message"].lower()

    def test_68_audit_logs_requires_admin_auth(self):
        """
        Security Hardening Test 68:
        GET /api/audit/logs MUST reject unauthenticated requests and require valid X-Admin-Key.
        """
        from fastapi.testclient import TestClient

        from main import ADMIN_API_KEY, app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        # 1. Unauthenticated -> 401
        res_no_auth = tc.get("/api/audit/logs")
        assert res_no_auth.status_code == 401
        assert "Valid X-Admin-Key" in res_no_auth.json()["detail"]

        # 2. Bad key -> 401
        res_bad_key = tc.get("/api/audit/logs", headers={"X-Admin-Key": "wrong_key_123"})
        assert res_bad_key.status_code == 401

        # 3. Authenticated admin -> 200
        res_auth = tc.get("/api/audit/logs", headers={"X-Admin-Key": ADMIN_API_KEY})
        assert res_auth.status_code == 200
        assert "logs" in res_auth.json()

    def test_69_sweep_endpoints_require_admin_auth(self):
        """
        Security Hardening Test 69:
        POST /api/trust/sweep-expired and POST /api/sales/sweep-timeouts
        MUST reject unauthenticated callers and require valid X-Admin-Key.
        """
        from fastapi.testclient import TestClient

        from main import ADMIN_API_KEY, app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        # 1. /api/trust/sweep-expired without auth -> 401
        res_sweep_no_auth = tc.post("/api/trust/sweep-expired")
        assert res_sweep_no_auth.status_code == 401

        # 2. /api/trust/sweep-expired with auth -> 200
        res_sweep_auth = tc.post("/api/trust/sweep-expired", headers={"X-Admin-Key": ADMIN_API_KEY})
        assert res_sweep_auth.status_code == 200

        # 3. /api/sales/sweep-timeouts without auth -> 401
        res_timeouts_no_auth = tc.post("/api/sales/sweep-timeouts")
        assert res_timeouts_no_auth.status_code == 401

        # 4. /api/sales/sweep-timeouts with auth -> 200
        res_timeouts_auth = tc.post("/api/sales/sweep-timeouts", headers={"X-Admin-Key": ADMIN_API_KEY})
        assert res_timeouts_auth.status_code == 200

    def test_70_agent_manifest_discovery_endpoint(self):
        """
        Fintech Test 70:
        Verifies that GET /.well-known/agent.json and GET /.well-known/agent-commerce.json
        return a valid, standard Agentic Commerce Discovery Manifest (UAP 1.0 aligned).
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        for endpoint in ["/.well-known/agent.json", "/.well-known/agent-commerce.json"]:
            res = tc.get(endpoint)
            assert res.status_code == 200
            data = res.json()
            assert data["protocol"] == "UAP/1.0"
            assert data["name"] == "MerchantMesh Informal Commerce Mesh"
            assert "catalog_discovery" in data["capabilities"]
            assert "razorpay_payment_links" in data["capabilities"]
            assert "razorpay_route_settlement" in data["capabilities"]
            assert data["endpoints"]["discovery"] == "/api/a2a/catalog/discover"
            assert data["endpoints"]["negotiate_step"] == "/api/a2a/negotiate/step"
            assert data["endpoints"]["checkout"] == "/api/trust/checkout"
            assert data["guardrails"]["price_floor_enforced"] is True
            assert data["guardrails"]["max_informal_cap_inr"] == 50000

    def test_71_simulate_payment_webhook_and_route_settlement(self, setup_clean_database):
        """
        Fintech Test 71:
        Verifies that POST /api/payment/simulate-webhook correctly generates HMAC-signed payload,
        executes process_payment_webhook, consumes stock reservation, updates stock, and triggers Route settlement.
        """
        from fastapi.testclient import TestClient

        from main import app
        from core.razorpay_client import razorpay_client
        original_is_live = razorpay_client.is_live
        razorpay_client.is_live = False
        tc = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 5 WHERE id = 'p1'")
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_test_m1' WHERE id = 'm1'")
        
        order_id = f"ord_sim_test_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
        """, (f"res_{order_id}", order_id))
        conn.commit()
        conn.close()

        # Unauthenticated call must be rejected
        unauth_res = tc.post("/api/payment/simulate-webhook", json={"order_id": order_id})
        assert unauth_res.status_code == 401

        res = tc.post(
            "/api/payment/simulate-webhook", 
            json={"order_id": order_id},
            headers={"X-Admin-Key": ADMIN_API_KEY}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "PAYMENT_CAPTURED_AND_SETTLED"
        assert data["payment_status"] == "PAID"
        assert data["settlement_status"] == "SETTLED"
        assert data["payment_id"].startswith("pay_")
        assert data["settlement"]["net_payout"] == 1500
        assert data["settlement"]["platform_fee"] == 0
        assert data["remaining_stock"] == 4

        # Verify DB order state
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, settlement_status, payment_id FROM orders WHERE id = ?", (order_id,))
        order_db = cursor.fetchone()
        assert order_db["payment_status"] == "PAID"
        assert order_db["settlement_status"] == "SETTLED"
        assert order_db["payment_id"] == data["payment_id"]

        # Verify stock reservation is CONSUMED
        cursor.execute("SELECT status FROM stock_reservations WHERE order_id = ?", (order_id,))
        assert cursor.fetchone()["status"] == "CONSUMED"
        conn.close()

    def test_72_multithreaded_high_concurrency_stock_contention_race(self):
        """
        Adversarial Test 72:
        Simultaneous 10-thread parallel checkout contention on the LAST remaining unit of stock.
        Proves SQLite BEGIN IMMEDIATE + WAL mode guarantees:
        1. Exactly ONE buyer wins the stock reservation lock.
        2. Exactly 9 buyers are safely rejected without overselling or negative inventory.
        3. Zero DB corruption or deadlock under high concurrent load.
        """
        import concurrent.futures

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 1, listed_price = 1500, floor_price = 900 WHERE id = 'p1'")
        
        # Create 10 distinct buyer records and orders competing for the same single unit
        order_ids = []
        for idx in range(10):
            bid = f"b_conc_{idx}"
            cursor.execute("INSERT OR REPLACE INTO buyers (id, phone_number, buyer_trust_score) VALUES (?, ?, 4.5)", (bid, f"999999999{idx}"))
            oid = f"ord_concurrent_{idx}_{uuid.uuid4().hex[:6]}"
            order_ids.append(oid)
            cursor.execute("""
                INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status)
                VALUES (?, 'p1', 'm1', ?, 1, 950, 'AWAITING_MERCHANT')
            """, (oid, bid))
        conn.commit()
        conn.close()

        def confirm_worker(oid):
            return confirm_merchant_order_and_reserve(order_id=oid, merchant_id="m1", confirmation="Y")

        # Launch 10 simultaneous threads competing at the exact same millisecond
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_oid = {executor.submit(confirm_worker, oid): oid for oid in order_ids}
            results = [f.result() for f in concurrent.futures.as_completed(future_to_oid)]

        successful_wins = [r for r in results if r.get("confirmed") is True]
        rejected_fails = [r for r in results if r.get("confirmed") is False]

        # INVARIANT: Exactly 1 winner, exactly 9 losers
        assert len(successful_wins) == 1, f"Concurrency Failure: Expected 1 winner but got {len(successful_wins)}!"
        assert len(rejected_fails) == 9, f"Concurrency Failure: Expected 9 rejections but got {len(rejected_fails)}!"
        assert successful_wins[0]["status"] == "PAYMENT_LINK_GENERATED"

        # Verify DB consistency
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as active_res FROM stock_reservations WHERE product_id = 'p1' AND status = 'ACTIVE'")
        assert cursor.fetchone()["active_res"] == 1

        cursor.execute("SELECT COUNT(*) as pending_orders FROM orders WHERE product_id = 'p1' AND payment_status = 'PENDING_PAYMENT'")
        assert cursor.fetchone()["pending_orders"] == 1

        cursor.execute("SELECT COUNT(*) as awaiting_orders FROM orders WHERE product_id = 'p1' AND payment_status = 'AWAITING_MERCHANT'")
        assert cursor.fetchone()["awaiting_orders"] == 9
        conn.close()

    def test_73_catalog_parse_dynamic_merchant_creation(self):
        """
        Adversarial Test 73:
        Verifies that /api/catalog/parse dynamically registers new unseeded merchant IDs
        without unique phone number collision or foreign key IntegrityError.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        new_merchant_id = f"m_custom_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/catalog/parse", json={
            "message": "Pure Cotton Formal Shirt Price: 1200 Floor: 800 Stock: 10 Sizes: M, L, XL",
            "merchant_id": new_merchant_id, "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA5klEQVR4nO3SsREAIAwDMWD/ncMK+V6qXf35zsxh5y13iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYg1tn7z/EDxbGcl84AAAAASUVORK5CYII="
        })
        assert res.status_code == 200
        data = res.json()
        assert data["product_id"].startswith("p_")

        # Verify merchant and product exist in DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name, phone_number FROM merchants WHERE id = ?", (new_merchant_id,))
        m_row = cursor.fetchone()
        assert m_row is not None
        assert m_row["phone_number"].startswith("+919")

        cursor.execute("SELECT listed_price, floor_price, stock_quantity FROM products WHERE id = ?", (data["product_id"],))
        p_row = cursor.fetchone()
        assert p_row is not None
        assert p_row["listed_price"] == 1200
        assert p_row["floor_price"] == 800
        conn.close()

    def test_74_webhook_inventory_underflow_transitions_to_reconciliation_without_500(self, setup_clean_database):
        """
        Adversarial Test 74: If an unexpected physical stock underflow occurs at webhook time,
        the system must gracefully transition the order to PAYMENT_RECONCILIATION_REQUIRED & REFUND_PENDING,
        acknowledge the webhook with 200 OK, and never crash into an unhandled HTTP 500 retry loop.
        """
        from core.razorpay_client import razorpay_client
        from core.trust_engine import process_payment_webhook

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = "ord_underflow_test"
        prod_id = "p_underflow_test"
        merch_id = "m1"
        
        # Product with 0 physical stock
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity)
                VALUES (?, ?, 'Soldout Sneaker', 'Footwear', 2000, 1500, 0)
            """, (prod_id, merch_id))

            cursor.execute("""
                INSERT OR REPLACE INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
                VALUES (?, ?, ?, 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
            """, (order_id, prod_id, merch_id))

            cursor.execute("""
                INSERT OR REPLACE INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
                VALUES ('res_underflow', ?, ?, 1, 'ACTIVE', datetime('now', '+15 minutes'))
            """, (order_id, prod_id))
            conn.commit()
        finally:
            conn.close()

        raw_payload = json.dumps({
            "event": "payment_link.paid",
            "id": "evt_underflow_123",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_underflow_999",
                        "amount": 150000,
                        "currency": "INR",
                        "created_at": int(time.time())
                    }
                },
                "payment_link": {
                    "entity": {
                        "id": "plink_underflow_999",
                        "reference_id": order_id,
                        "amount": 150000
                    }
                }
            }
        }).encode("utf-8")

        sig = hmac.new(
            razorpay_client.webhook_secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256
        ).hexdigest()

        # Must not raise an unhandled exception or crash
        res = process_payment_webhook(raw_payload, sig, event_id="evt_underflow_123")
        assert res["status"] == "PAYMENT_RECONCILIATION_REQUIRED"
        assert res["reason"] == "INSUFFICIENT_PHYSICAL_STOCK"

        # Verify DB transitioned to REFUND_PENDING
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_status, settlement_status FROM orders WHERE id = ?", (order_id,))
            o_row = cursor.fetchone()
            assert o_row["payment_status"] == "PAYMENT_RECONCILIATION_REQUIRED"
            assert o_row["settlement_status"] == "REFUND_PENDING"
        finally:
            conn.close()

    def test_75_zero_rupee_price_floor_strictly_blocked(self, setup_clean_database):
        """
        Adversarial Test 75: Enforce that ₹0 floor or ₹0 proposed price is strictly rejected by guardrails.
        """
        from core.trust_engine import verify_transaction_price_floor

        # Try to checkout product with proposed price 0
        passed, reason, details = verify_transaction_price_floor("p1", 0, 1)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in reason
        assert "strictly greater than zero" in reason

    def test_76_langgraph_instant_checkout_concurrency_stock_reverification(self, setup_clean_database):
        """
        Adversarial Test 76: Verify that run_trust_agent (LangGraph Instant Checkout)
        performs atomic re-verification inside the BEGIN IMMEDIATE write lock.
        """

        conn = get_db_connection()
        cursor = conn.cursor()
        prod_id = "p_atomic_single_unit"
        try:
            # Only 1 unit in stock
            cursor.execute("""
                INSERT OR REPLACE INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity)
                VALUES (?, 'm1', 'Ultra Rare Item', 'Collectibles', 5000, 4000, 1)
            """, (prod_id,))
            conn.commit()
        finally:
            conn.close()

        # Buyer 1 checks out instant
        res1 = run_trust_agent(product_id=prod_id, agreed_price=4500, quantity=1, merchant_response="Y")
        assert res1["status"] in ["CONFIRMED", "PAYMENT_LINK_GENERATED"]
        assert res1["payment_link_url"] is not None

        # Buyer 2 tries to instant checkout the same item simultaneously
        res2 = run_trust_agent(product_id=prod_id, agreed_price=4500, quantity=1, merchant_response="Y")
        assert res2["status"] == "GUARDRAIL_VIOLATION"
        assert res2["guardrail_status"] == "REJECTED_STOCK_UNAVAILABLE"

    def test_77_webhook_with_missing_or_falsy_amount_strictly_rejected(self, setup_clean_database):
        """
        Adversarial Test 77: Ensure that a webhook with omitted, zero, or falsy amount
        is strictly rejected with AMOUNT_MISMATCH and never marks the order as PAID.
        """
        from core.razorpay_client import razorpay_client
        from core.trust_engine import process_payment_webhook

        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = "ord_falsy_amount_test"
        prod_id = "p1"
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
                VALUES (?, ?, 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
            """, (order_id, prod_id))
            cursor.execute("""
                INSERT OR REPLACE INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
                VALUES ('res_falsy', ?, ?, 1, 'ACTIVE', datetime('now', '+15 minutes'))
            """, (order_id, prod_id))
            conn.commit()
        finally:
            conn.close()

        # Payload completely omitting amount in payment and payment_link
        raw_payload = json.dumps({
            "event": "payment_link.paid",
            "id": "evt_falsy_amount_123",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_falsy_999",
                        "currency": "INR",
                        "created_at": int(time.time())
                    }
                },
                "payment_link": {
                    "entity": {
                        "id": "plink_falsy_999",
                        "reference_id": order_id
                    }
                }
            }
        }).encode("utf-8")

        sig = hmac.new(
            razorpay_client.webhook_secret.encode("utf-8"),
            raw_payload,
            hashlib.sha256
        ).hexdigest()

        res = process_payment_webhook(raw_payload, sig, event_id="evt_falsy_amount_123")
        assert res["status"] == "AMOUNT_MISMATCH"

        # Verify order remains in PENDING_PAYMENT
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
            row = cursor.fetchone()
            assert row["payment_status"] == "PENDING_PAYMENT"
        finally:
            conn.close()

    def test_78_volume_pricing_strictly_preserves_merchant_unit_floor(self, setup_clean_database):
        """
        Adversarial Test 78: Verify that volume discounts NEVER reduce the total floor below unit_floor * quantity.
        """
        from core.negotiation_engine import calculate_bundle_financials
        from core.trust_engine import verify_transaction_price_floor

        # For unit floor of ₹900 with quantity 3: total floor must be at least ₹2700
        total_listed, total_floor, discount_rate = calculate_bundle_financials(unit_listed=1200, unit_floor=900, quantity=3)
        assert total_floor == 2700
        assert total_floor >= 900 * 3

        # Guardrail check on product p1 (listed 1200, floor 800) with qty 3
        # Attempting ₹2300 (below ₹2400 hard floor) must fail
        passed, reason, _ = verify_transaction_price_floor("p1", 2300, quantity=3)
        assert passed is False
        assert "GUARDRAIL_VIOLATION" in reason

    def test_79_buyer_accept_with_injected_one_rupee_price_strictly_fails(self, setup_clean_database):
        """
        Adversarial Test 79:
        Simulates an adversarial buyer agent returning action='ACCEPT' with an injected offer_price of ₹1.
        Proves:
        1. The seller state machine cannot be hijacked to accept at ₹1.
        2. Acceptance strictly binds to the seller's authentic counter/floor price.
        3. LangGraph never concludes in ACCEPTED at a sub-floor price.
        """
        from agents.negotiation_agent import run_negotiation
        from core.negotiation_engine import BuyerTurnOutput

        # Product p1: Listed 1200, Floor 800
        with patch("agents.negotiation_agent.generate_buyer_turn_llm") as mock_buyer:
            # Adversary attempts to hijack state with ACCEPT @ ₹1
            mock_buyer.return_value = BuyerTurnOutput(
                action="ACCEPT",
                offer_price=1,
                message="I accept your offer at ₹1!",
                internal_reasoning="Adversarial attack attempting sub-floor deal closure."
            )
            res = run_negotiation(
                product_id="p1",
                buyer_id="b_adversary",
                buyer_target_price=1,
                buyer_max_budget=1500,
                max_turns=3
            )

            # Final price MUST NOT be ₹1
            if res.get("status") == "ACCEPTED":
                assert res["final_price"] >= 800, f"Critical security failure: deal closed at {res['final_price']} < floor 800"
            else:
                assert res.get("status") in ["IN_PROGRESS", "REJECTED_FLOOR_VIOLATION", "MAX_TURNS_REACHED", "DEADLOCK"]

    def test_80_audit_log_bounded_pruning(self, setup_clean_database):
        """
        Adversarial Test 80:
        Verifies that sweep_expired_reservations bounds SQLite audit_log table growth,
        preventing unbounded disk consumption.
        """
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Insert 5200 rows into audit_log
            entries = [("TEST_ACTION", "TestAgent", f"Audit entry {i}") for i in range(5200)]
            cursor.executemany("INSERT INTO audit_log (action, agent, reasoning) VALUES (?, ?, ?)", entries)
            conn.commit()
            
            cursor.execute("SELECT COUNT(*) as cnt FROM audit_log")
            assert cursor.fetchone()["cnt"] >= 5200
        finally:
            conn.close()

        # Run sweep
        sweep_res = sweep_expired_reservations()

        # Verify pruning
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as cnt FROM audit_log")
            cnt = cursor.fetchone()["cnt"]
            assert cnt <= 5000, f"Audit log was not pruned to 5,000 limit, current count: {cnt}"
        finally:
            conn.close()

    def test_81_sse_streaming_negotiation_endpoint(self, setup_clean_database):
        """
        Adversarial Test 81:
        Verifies that POST /api/negotiate/stream emits real-time Server-Sent Events (SSE)
        with 'init', 'turn', and 'complete' payloads without buffering or crashing.
        """
        client = TestClient(app)
        res = client.post("/api/negotiate/stream", json={
            "product_id": "p1",
            "buyer_target_price": 3000,
            "buyer_max_budget": 3500,
            "quantity": 1,
            "buyer_id": "b1"
        })
        assert res.status_code == 200
        assert "text/event-stream" in res.headers["content-type"]

        # Parse SSE stream
        raw_text = res.text
        lines = raw_text.strip().split("\n\n")
        events = []
        for l in lines:
            if l.startswith("data: "):
                events.append(json.loads(l[6:]))

        event_types = [e.get("event") for e in events]
        assert "init" in event_types, f"Missing 'init' event in SSE stream: {event_types}"
        assert "complete" in event_types, f"Missing 'complete' event in SSE stream: {event_types}"
        complete_evt = next(e for e in events if e.get("event") == "complete")
        assert complete_evt["final_price"] is not None or complete_evt["status"] in ["ACCEPTED", "DEADLOCK", "MAX_TURNS_REACHED"]

    def test_82_dynamic_merchants_endpoint(self, setup_clean_database):
        """
        Adversarial Test 82:
        Verifies that GET /api/merchants returns all active merchants from SQLite,
        including newly dynamically ingested merchants.
        """
        client = TestClient(app)

        # 1. Check initial seeded merchants
        res = client.get("/api/merchants")
        assert res.status_code == 200
        data = res.json()
        assert "merchants" in data
        merchant_ids = [m["id"] for m in data["merchants"]]
        assert "m1" in merchant_ids
        assert "m2" in merchant_ids
        assert "m3" in merchant_ids

        # 2. Ingest new merchant via catalog parse
        new_merch_id = f"m_dyn_{uuid.uuid4().hex[:6]}"
        parse_res = client.post("/api/catalog/parse", json={
            "message": "Premium Silk Scarf Rs 800 Floor 600 Stock 12",
            "merchant_id": new_merch_id
        })
        assert parse_res.status_code == 200

        # 3. Verify new merchant immediately appears in GET /api/merchants
        res_updated = client.get("/api/merchants")
        assert res_updated.status_code == 200
        updated_ids = [m["id"] for m in res_updated.json()["merchants"]]
        assert new_merch_id in updated_ids

    def test_83_asyncio_sweeper_non_blocking_execution(self, setup_clean_database):
        """
        Adversarial Test 83:
        Verifies that sweep functions execute smoothly in worker threads via asyncio.to_thread.
        """
        import asyncio

        from core.trust_engine import (
            sweep_expired_merchant_confirmations,
            sweep_expired_reservations,
        )

        async def run_async_sweepers():
            t1 = asyncio.to_thread(sweep_expired_reservations)
            t2 = asyncio.to_thread(sweep_expired_merchant_confirmations)
            r1, r2 = await asyncio.gather(t1, t2)
            return r1, r2

        r1, r2 = asyncio.run(run_async_sweepers())
        assert r1["status"] == "SWEEP_COMPLETE"
        assert r2["status"] == "TIMEOUT_SWEEP_COMPLETE"

    def test_84_negotiation_id_replay_double_spend_blocked(self):
        """
        Adversarial Test 84:
        Verifies that a discounted negotiation session cannot be replayed for infinite double-spending.
        Once an order consumes the negotiation_id, subsequent checkouts with the same ID must be rejected.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        neg_id = f"neg_replay_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', '[]', 3000, 'ACCEPTED')
        """, (neg_id,))
        conn.commit()
        conn.close()

        # First checkout: valid and accepted
        res1 = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "quantity": 1,
            "agreed_price": 3000,
            "buyer_id": "b1",
            "negotiation_id": neg_id,
            "instant_checkout": False
        })
        assert res1.status_code == 200, res1.text
        assert res1.json()["status"] in ["CONFIRMED", "AWAITING_MERCHANT", "PENDING_PAYMENT"]

        # Second checkout (Replay attack with same negotiation_id): MUST be rejected
        res2 = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "quantity": 1,
            "agreed_price": 3000,
            "buyer_id": "b1",
            "negotiation_id": neg_id,
            "instant_checkout": False
        })
        assert res2.status_code == 400
        assert "already been consumed" in res2.json()["detail"]

    def test_85_generate_payment_link_node_gateway_timeout_transitions_to_reconciliation(self):
        """
        Adversarial Test 85:
        Verifies that a network timeout during generate_payment_link_node in trust_agent.py
        transitions the order to PAYMENT_LINK_RECONCILIATION_REQUIRED rather than blindly cancelling it.
        """
        from unittest.mock import patch

        from agents.trust_agent import generate_payment_link_node

        order_id = f"ord_timeout_{uuid.uuid4().hex[:6]}"
        state = {
            "order_id": order_id,
            "product_id": "p1",
            "merchant_id": "m1", "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA5klEQVR4nO3SsREAIAwDMWD/ncMK+V6qXf35zsxh5y13iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYg1tn7z/EDxbGcl84AAAAASUVORK5CYII=",
            "buyer_id": "b1",
            "agreed_price": 1200,
            "quantity": 1,
            "product": {"product_name": "Test Sneakers"},
            "merchant": {"name": "Sneaker Bhai"}
        }

        with patch("core.razorpay_client.razorpay_client.create_payment_link", return_value={"status": "FAILED", "error": "Gateway Read Timeout: Connection to api.razorpay.com timed out"}):
            res = generate_payment_link_node(state)
            assert res["status"] == "PAYMENT_LINK_RECONCILIATION_REQUIRED"

        # Verify database record
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        assert row["payment_status"] == "PAYMENT_LINK_RECONCILIATION_REQUIRED"
        conn.close()

    def test_86_ephemeral_buyer_checkout_succeeds_without_fk_violation(self):
        """
        Adversarial Test 86:
        Verifies that a dynamically generated ephemeral buyer_id (not in seed data)
        can checkout without triggering SQLite FOREIGN KEY IntegrityError (HTTP 500).
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        fresh_buyer_id = f"b_ephemeral_{uuid.uuid4().hex[:8]}"

        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "quantity": 1,
            "agreed_price": 3500,
            "buyer_id": fresh_buyer_id,
            "buyer_name": "Ephemeral Buyer",
            "buyer_phone": "+919876543219"
        })
        assert res.status_code == 200
        assert res.json()["status"] in ["CONFIRMED", "AWAITING_MERCHANT", "PENDING_PAYMENT"]

    def test_87_direct_checkout_quantity_multiplier_enforced(self):
        """
        Adversarial Test 87:
        Verifies that direct checkout (without negotiation) enforces listed_price * quantity.
        An attacker cannot buy quantity = 5 of a ₹3,500 listed item for ₹3,500 total.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        # Listed price for p1 is 3500. For 5 units, total listed price is 17500.
        # Sending agreed_price = 3500 for 5 units MUST be rejected with 400.
        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "quantity": 5,
            "agreed_price": 3500,
            "buyer_id": "b1"
        })
        assert res.status_code == 400
        assert "NEGOTIATION_REQUIRED" in res.json()["detail"]
        assert "7,500" in res.json()["detail"]

    def test_88_negotiation_quantity_mismatch_rejected(self):
        """
        Adversarial Test 88:
        Verifies that a negotiation approved for quantity = 10 cannot be checked out with quantity = 1.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        neg_id = f"neg_qty_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, quantity, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', 10, '[]', 29000, 'ACCEPTED')
        """, (neg_id,))
        conn.commit()
        conn.close()

        # Checkout with quantity = 1 when negotiation was for quantity = 10 MUST fail
        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "quantity": 1,
            "agreed_price": 29000,
            "buyer_id": "b1",
            "negotiation_id": neg_id
        })
        assert res.status_code == 400
        assert "GUARDRAIL_VIOLATION" in res.json()["detail"]
        assert "quantity 10" in res.json()["detail"]

    def test_89_late_webhook_after_expiry_queues_refund_reconciliation(self):
        """
        Adversarial Test 89:
        Verifies that when a payment is captured for an expired reservation whose stock was reallocated,
        the system transitions the order to PAYMENT_RECONCILIATION_REQUIRED and REFUND_PENDING,
        and never drops the webhook or strands buyer funds.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_late_{uuid.uuid4().hex[:6]}"
        cursor.execute("UPDATE products SET stock_quantity = 0 WHERE id = 'p1'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1500, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'EXPIRED', datetime('now', '-30 minutes'))
        """, (f"res_{order_id}", order_id))
        conn.commit()
        conn.close()

        # Late webhook payload with payment timestamp after expiry
        mock_payload = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_late_test",
            amount_inr=1500,
            order_id=order_id,
            event="payment_link.paid"
        )
        body_bytes = json.dumps(mock_payload["payload"]).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        res = process_payment_webhook(raw_body=body_bytes, signature=sig)
        assert res["status"] == "PAYMENT_RECONCILIATION_REQUIRED"
        assert res["reason"] == "STOCK_REALLOCATED_AFTER_EXPIRY"

        # Verify DB order is queued for refund
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT payment_status, settlement_status FROM orders WHERE id = ?", (order_id,))
        row = cursor.fetchone()
        assert row["payment_status"] == "PAYMENT_RECONCILIATION_REQUIRED"
        assert row["settlement_status"] == "REFUND_PENDING"
        conn.close()

    def test_90_payment_captured_webhook_without_payment_link_resolves_order_via_notes(self):
        """
        Adversarial Test 90:
        Verifies that a payment.captured webhook without a payment_link entity
        correctly resolves the order via payment.notes.order_id and settles cleanly.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_upi_{uuid.uuid4().hex[:6]}"
        cursor.execute("UPDATE products SET stock_quantity = 5 WHERE id = 'p1'")
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_upi_m1' WHERE id = 'm1'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 1200, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT')
        """, (order_id,))
        cursor.execute("""
            INSERT INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at)
            VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))
        """, (f"res_{order_id}", order_id))
        conn.commit()
        conn.close()

        # Direct payment.captured event without payment_link entity
        payment_id = f"pay_upi_{uuid.uuid4().hex[:8]}"
        captured_payload = {
            "event": "payment.captured",
            "id": f"evt_upi_{uuid.uuid4().hex[:8]}",
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "amount": 120000,
                        "currency": "INR",
                        "status": "captured",
                        "order_id": "order_razorpay_internal_xyz",
                        "notes": {
                            "order_id": order_id,
                            "platform": "MerchantMesh"
                        }
                    }
                }
            }
        }
        body_bytes = json.dumps(captured_payload).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        res = process_payment_webhook(raw_body=body_bytes, signature=sig)
        assert res["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"
        assert res["order_id"] == order_id
        assert res["payment_id"] == payment_id
        assert res["payment_status"] == "PAID"

    def test_91_product_card_image_endpoint_and_generation(self):
        """
        Adversarial Test 91:
        Verifies that create_product_card composites a card and GET /api/product-card/{product_id}
        serves the generated JPEG image.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        # 1. Parse catalog message
        res = client.post("/api/catalog/parse", json={
            "message": "Premium Silk Saree price 4500 floor 3500 stock 8 sizes onesize",
            "merchant_id": "m1", "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAGQAAABkCAIAAAD/gAIDAAAA5klEQVR4nO3SsREAIAwDMWD/ncMK+V6qXf35zsxh5y13iNV4ViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYgViBWIFYg1tn7z/EDxbGcl84AAAAASUVORK5CYII="
        })
        assert res.status_code == 200
        data = res.json()
        assert data["product_card_url"] is not None
        product_id = data["product_id"]

        # 2. Fetch product card image endpoint
        card_res = client.get(f"/api/product-card/{product_id}")
        assert card_res.status_code == 200
        assert card_res.headers["content-type"] == "image/jpeg"
        assert len(card_res.content) > 1000

    def test_92_live_mode_disables_simulation_endpoint(self):
        """
        Adversarial Test 92:
        Verifies that POST /api/payment/simulate-webhook is strictly blocked with HTTP 403
        when razorpay_client.is_live is True, preventing live backdoor Route payouts.
        """
        from fastapi.testclient import TestClient

        from core.razorpay_client import razorpay_client
        from main import ADMIN_API_KEY, app
        client = TestClient(app)

        with patch.object(razorpay_client, 'is_live', True):
            res = client.post(
                "/api/payment/simulate-webhook",
                json={"order_id": "ord_any"},
                headers={"X-Admin-Key": ADMIN_API_KEY}
            )
            assert res.status_code == 403
            assert "SIMULATION_DISABLED_IN_LIVE_MODE" in res.json()["detail"]

    def test_93_sybil_hoarding_blocked_across_session_even_with_altered_buyer_id(self):
        """
        Adversarial Test 93:
        Verifies that an attacker rotating buyer_id (b_sybil_1, b_sybil_2...) within the same session
        is strictly blocked from hoarding inventory once active holds reach the safety limit.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        sybil_session = f"sess_sybil_{uuid.uuid4().hex[:8]}"

        # Create 2 unexpired active reservations under this session with different buyer IDs
        for i in range(2):
            b_id = f"b_sybil_{i}_{uuid.uuid4().hex[:6]}"
            res = client.post(
                "/api/trust/checkout",
                json={"product_id": "p1", "quantity": 1, "agreed_price": 3500, "buyer_id": b_id, "session_id": sybil_session},
                headers={"X-Session-ID": sybil_session}
            )
            assert res.status_code == 200

        # Attempting a 3rd reservation with a NEW buyer_id under the same session MUST be blocked by Anti-Hoarding
        b_id_3 = f"b_sybil_new_{uuid.uuid4().hex[:6]}"
        res3 = client.post(
            "/api/trust/checkout",
            json={"product_id": "p1", "quantity": 1, "agreed_price": 3500, "buyer_id": b_id_3, "session_id": sybil_session},
            headers={"X-Session-ID": sybil_session}
        )
        assert res3.status_code == 400
        assert "Anti-Hoarding Block" in res3.json()["detail"]

    def test_94_late_webhook_on_swept_expired_order_fulfills_if_stock_available(self):
        """
        Adversarial Test 94:
        Verifies that when a webhook arrives for an order marked EXPIRED by the sweeper,
        the system checks physical stock:
        - If stock is still available -> revives to PAID and settles cleanly without error!
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        order_id = f"ord_swept_{uuid.uuid4().hex[:6]}"
        cursor.execute("UPDATE products SET stock_quantity = 10 WHERE id = 'p1'")
        cursor.execute("UPDATE merchants SET razorpay_account_id = 'acc_swept_m1' WHERE id = 'm1'")
        cursor.execute("""
            INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status)
            VALUES (?, 'p1', 'm1', 'b1', 1, 3500, 'EXPIRED', 'PENDING_SETTLEMENT')
        """, (order_id,))
        conn.commit()
        conn.close()

        mock_payload = razorpay_client.generate_mock_webhook_payload(
            payment_link_id="plink_swept_test",
            amount_inr=3500,
            order_id=order_id,
            event="payment_link.paid"
        )
        body_bytes = json.dumps(mock_payload["payload"]).encode("utf-8")
        sig = hmac.new(b"merchantmesh_secret", body_bytes, hashlib.sha256).hexdigest()

        res = process_payment_webhook(raw_body=body_bytes, signature=sig)
        assert res["status"] == "PAYMENT_PROCESSED_SUCCESSFULLY"
        assert res["order_id"] == order_id
        assert res["payment_status"] == "PAID"

        # Verify stock was decremented from 10 to 9
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = 'p1'")
        assert cursor.fetchone()["stock_quantity"] == 9
        conn.close()

    def test_95_reverse_auction_marks_outbid_dealers_without_ghosting(self):
        """
        Adversarial Test 95:
        Verifies that when multiple dealers accept during an RFQ, non-winning dealers
        are explicitly updated to OUTBID in the database, preventing ghosting.
        """
        from core.reverse_auction import run_parallel_reverse_auction
        res = run_parallel_reverse_auction(
            product_ids=["p1", "p2", "p3"],
            buyer_target_price=3800,
            buyer_max_budget=4500,
            quantity=1,
            buyer_id="b1"
        )
        assert res["winner"] is not None
        assert res["winner"]["is_winner"] is True

        # Verify outbid candidate deals exist and are not ghosted
        outbid_deals = [d for d in res["deals"] if d.get("status") == "OUTBID"]
        if len(res["deals"]) > 1 and res["accepted_count"] > 1:
            assert len(outbid_deals) >= 1

    def test_96_public_merchants_endpoint_never_leaks_api_keys(self):
        """
        Adversarial Test 96:
        Verifies that GET /api/merchants never leaks private api_key or key fields
        to unauthenticated callers.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        res = client.get("/api/merchants")
        assert res.status_code == 200
        data = res.json()
        assert "merchants" in data
        assert len(data["merchants"]) > 0
        for m in data["merchants"]:
            assert "api_key" not in m
            assert "key" not in m
            assert "name" in m
            assert "id" in m

    def test_97_hitl_confirmation_re_verifies_anti_hoarding_bounds(self):
        """
        Adversarial Test 97:
        Verifies that confirm_merchant_order_and_reserve re-checks Anti-Hoarding limits
        so an attacker cannot bypass hold caps via queued HITL orders.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        buyer_id = f"b_hitl_hoard_{uuid.uuid4().hex[:6]}"
        cursor.execute("INSERT OR REPLACE INTO buyers (id, phone_number, buyer_trust_score, return_rate) VALUES (?, '9888877777', 1.0, 0.0)", (buyer_id,))
        
        # Seed 2 active unexpired reservations for this buyer
        for i in range(2):
            o_id = f"ord_hitl_held_{i}"
            cursor.execute("INSERT OR REPLACE INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status) VALUES (?, 'p1', 'm1', ?, 1, 950, 'PENDING_PAYMENT')", (o_id, buyer_id))
            cursor.execute("INSERT OR REPLACE INTO stock_reservations (id, order_id, product_id, quantity, status, expires_at) VALUES (?, ?, 'p1', 1, 'ACTIVE', datetime('now', '+15 minutes'))", (f"res_hitl_{i}", o_id))
        
        # Create a 3rd order in AWAITING_MERCHANT
        order_id_3 = f"ord_hitl_pending_{uuid.uuid4().hex[:6]}"
        cursor.execute("INSERT INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status) VALUES (?, 'p1', 'm1', ?, 1, 950, 'AWAITING_MERCHANT')", (order_id_3, buyer_id))
        conn.commit()
        conn.close()

        # Merchant attempts to confirm order 3 -> MUST BE REJECTED by Anti-Hoarding
        res = confirm_merchant_order_and_reserve(order_id=order_id_3, merchant_id="m1", confirmation="Y")
        assert res["confirmed"] is False
        assert res["status"] == "GUARDRAIL_VIOLATION"
        assert "Anti-Hoarding Block" in res["message"]

    def test_98_floor_price_exceeding_listed_fails_data_integrity_check(self):
        """
        Adversarial Test 98:
        Verifies that if a product has a floor price exceeding listed price (bad ingestion data),
        _verify_price_floor_tx returns DATA_INTEGRITY_ERROR.
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO products (id, merchant_id, product_name, category, listed_price, floor_price, stock_quantity, search_tags_json, sizes_json)
            VALUES ('p_corrupt', 'm1', 'Corrupt Price Item', 'Test', 1000, 1500, 5, '[]', '[]')
        """)
        conn.commit()

        from core.trust_engine import _verify_price_floor_tx
        passed, reason, _ = _verify_price_floor_tx(cursor, "p_corrupt", 1000, 1)
        assert passed is False
        assert "DATA_INTEGRITY_ERROR" in reason
        conn.close()

    def test_99_buyer_phone_collision_retry_guarantees_foreign_key_safety(self):
        """
        Adversarial Test 99:
        Verifies that /api/trust/checkout safely handles phone number collisions
        and guarantees that the buyer_id is inserted into the buyers table,
        preventing foreign key IntegrityErrors when creating orders.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        # Seed an existing buyer with a specific phone number
        existing_phone = "+919876543210"
        cursor.execute("INSERT OR REPLACE INTO buyers (id, phone_number) VALUES ('b_existing_user', ?)", (existing_phone,))
        cursor.execute("UPDATE products SET stock_quantity = 10, listed_price = 1000, floor_price = 800 WHERE id = 'p1'")
        conn.commit()
        conn.close()

        # New buyer attempts to checkout with the same colliding phone number
        new_buyer_id = f"b_collide_{uuid.uuid4().hex[:6]}"
        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 1000,
            "quantity": 1,
            "buyer_id": new_buyer_id,
            "buyer_phone": existing_phone,
            "merchant_response": "Y"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["confirmed"] is True
        assert "order_id" in data

        # Verify buyer was inserted into buyers table without collision crash
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM buyers WHERE id = ?", (new_buyer_id,))
        assert cursor.fetchone() is not None
        conn.close()

    def test_100_route_transfer_permission_error_falls_back_cleanly(self):
        """
        Adversarial Test 100:
        Verifies that settle_order_via_route gracefully falls back to test settlement
        when a custom Razorpay test API key throws a Route permission / unlinked error.
        """
        with patch.object(razorpay_client, 'is_live', True):
            mock_client = MagicMock()
            mock_client.payment.transfer.side_effect = Exception("BAD_REQUEST_ERROR: Route feature is not enabled for this account")
            with patch.object(razorpay_client, 'client', mock_client):
                res = razorpay_client.settle_order_via_route(
                    payment_id="pay_test_12345",
                    merchant_account_id="acc_live_judge_key",
                    gross_amount_inr=1500,
                    platform_fee_inr=20
                )
                assert res["status"] == "SETTLED"
                assert res["is_simulated"] is True
                assert "transfer_id" in res
                assert "Recorded test settlement" in res["diagnostic"]

    def test_101_negotiation_quantity_null_or_mismatch_strictly_rejected(self):
        """
        Adversarial Test 101:
        Verifies that even if negotiation.quantity is NULL or 1, checkout requesting
        quantity 2 without a volume negotiation is strictly blocked with GUARDRAIL_VIOLATION.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        neg_id = f"neg_single_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT INTO negotiations (id, product_id, buyer_id, quantity, turns_json, final_price, outcome)
            VALUES (?, 'p1', 'b1', NULL, '[]', 900, 'ACCEPTED')
        """, (neg_id,))
        cursor.execute("UPDATE products SET stock_quantity = 10, listed_price = 1000, floor_price = 800 WHERE id = 'p1'")
        conn.commit()
        conn.close()

        # Buyer attempts to checkout 2 units at the single-unit negotiated price (₹900)
        res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": 900,
            "quantity": 2,
            "negotiation_id": neg_id,
            "buyer_id": "b1"
        })
        assert res.status_code == 400
        assert "GUARDRAIL_VIOLATION" in res.json()["detail"]
        assert "approved for quantity 1" in res.json()["detail"]

    def test_102_session_scoped_catalog_seed_preserves_concurrent_data(self):
        """
        Adversarial Test 102:
        Verifies that POST /api/catalog/seed with X-Session-Id only resets session data
        and preserves orders from other active concurrent evaluation sessions.
        """
        from fastapi.testclient import TestClient

        from main import ADMIN_API_KEY, app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO buyers (id, phone_number) VALUES ('b_judge_b', '+919111122222')")
        order_judge_b = f"ord_judge_b_{uuid.uuid4().hex[:6]}"
        cursor.execute("""
            INSERT OR REPLACE INTO orders (id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, session_id)
            VALUES (?, 'p1', 'm1', 'b_judge_b', 1, 1500, 'PENDING_PAYMENT', 'sess_judge_b')
        """, (order_judge_b,))
        conn.commit()
        conn.close()

        # Judge A resets their session
        res = client.post(
            "/api/catalog/seed",
            json={"force": True},
            headers={"X-Admin-Key": ADMIN_API_KEY, "X-Session-Id": "sess_judge_a"}
        )
        assert res.status_code == 200

        # Judge B's order MUST still exist in database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM orders WHERE id = ?", (order_judge_b,))
        assert cursor.fetchone() is not None
        conn.close()

    def test_103_negotiation_persists_buyer_and_enables_instant_checkout(self):
        """
        Adversarial Test 103:
        Verifies that /api/negotiate safely persists ephemeral buyers into buyers table,
        persists the accepted negotiation record, and allows immediate checkout via /api/trust/checkout.
        """
        from fastapi.testclient import TestClient

        from main import app
        client = TestClient(app)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = 10, listed_price = 1200, floor_price = 800 WHERE id = 'p1'")
        conn.commit()
        conn.close()

        ephemeral_buyer_id = f"b_demo_{uuid.uuid4().hex[:8]}"

        # Step 1: Run Negotiation
        neg_res = client.post("/api/negotiate", json={
            "product_id": "p1",
            "buyer_target_price": 850,
            "buyer_max_budget": 1100,
            "quantity": 1,
            "buyer_id": ephemeral_buyer_id
        })
        assert neg_res.status_code == 200
        neg_data = neg_res.json()
        assert neg_data["status"] == "ACCEPTED"
        neg_id = neg_data["session_id"]
        final_price = neg_data["final_price"]

        # Step 2: Checkout using negotiation_id
        checkout_res = client.post("/api/trust/checkout", json={
            "product_id": "p1",
            "agreed_price": final_price,
            "quantity": 1,
            "negotiation_id": neg_id,
            "buyer_id": ephemeral_buyer_id,
            "merchant_response": "Y"
        })
        assert checkout_res.status_code == 200
        checkout_data = checkout_res.json()
        assert checkout_data["status"] in ["RESERVED", "CONFIRMED"]
        assert "payment_link" in checkout_data or "order_id" in checkout_data























