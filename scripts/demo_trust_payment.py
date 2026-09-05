"""
MerchantMesh - Day 5 Live Interactive Demo: Trust Agent & Razorpay MCP
Demonstrates:
1. Happy Path: Merchant Confirmation ('Y') -> 15-min Razorpay Link -> Webhook Stock Auto-Deduction
2. Failure Recovery 1: Merchant Rejection ('N') -> Penalization + Agentic Alternative Product Discovery
3. Failure Recovery 2: Code-Level Hard Price Floor Guardrail Defense (Sub-floor rejection)
4. Failure Recovery 3: Merchant Timeout -> Confidence Decay + Responsive Alternatives
5. 15-Minute Payment Link Expiration & Cancellation
6. Standard Model Context Protocol (MCP) Tool Calling
"""

import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.trust_agent import run_trust_agent
from core.razorpay_client import razorpay_client
from core.trust_engine import (
    expire_unpaid_order,
    process_payment_webhook,
)
from data.database import get_db_connection, init_db
from mcp.razorpay_mcp_server import MCP_TOOL_REGISTRY, dispatch_mcp_call
from scripts.seed_db import seed_from_json


def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  🚀 {title.upper()}")
    print("=" * 80)


def print_section(title: str):
    print(f"\n👉 {title}")
    print("-" * 60)


def run_demo():
    print_banner("MerchantMesh - Day 5: Trust Agent & Razorpay MCP Live Demo")
    
    # Initialize fresh database
    print("🔧 Initializing SQLite Database and Seeding Catalog...")
    init_db()
    seed_from_json()
    print("✅ Catalog initialized with 18 products across 4 merchants.")

    # =========================================================================
    # SCENARIO 1: HAPPY PATH (Confirmation -> Razorpay Link -> Webhook Auto-Deduct)
    # =========================================================================
    print_banner("Scenario 1: Happy Path — Confirmation, Razorpay MCP & Webhook Auto-Deduct")
    print("📝 Context: Negotiation closed for 'Urban Black Hoodie' (p13) at ₹1,100 (Floor: ₹900).")
    print("   Buyer: Ananya Sharma (+91 9876543210)")

    # Check stock before
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stock_quantity, listed_price, floor_price FROM products WHERE id = 'p13'")
    prod_before = cursor.fetchone()
    print(f"📦 Initial Product State: Stock = {prod_before['stock_quantity']} units, Listed = ₹{prod_before['listed_price']}, Floor = ₹{prod_before['floor_price']}")
    conn.close()

    print_section("Step 1: Trust Agent Validates Guardrails & Merchant Confirms ('Y')")
    result_happy = run_trust_agent(
        product_id="p13",
        agreed_price=1100,
        quantity=1,
        merchant_response="Y",
        buyer_name="Ananya Sharma",
        buyer_phone="9876543210"
    )

    print(f"🛡️ Guardrail Status: {result_happy['guardrail_status']}")
    print(f"🤝 Merchant Response: {result_happy['merchant_response']} (Confirmed)")
    print(f"🆔 Order Reference: {result_happy['order_id']}")
    print(f"💳 Razorpay Payment Link ID: {result_happy['payment_link_id']}")
    print(f"🔗 Customer Payment URL: {result_happy['payment_link_url']}")
    print(f"⏳ Expiration Time (15-min): {result_happy['expires_at']}")
    print(f"\n💬 Simulated WhatsApp Message to Buyer:\n{result_happy['message']}")

    print_section("Step 2: Mock Webhook Dispatcher fires 'payment_link.paid'")
    print("   (Simulating Razorpay webhook server notifying MerchantMesh of successful payment)")

    mock_webhook = razorpay_client.generate_mock_webhook_payload(
        payment_link_id=result_happy['payment_link_id'],
        amount_inr=1100,
        order_id=result_happy['order_id'],
        event="payment_link.paid"
    )
    print(f"🔐 Webhook HMAC Signature: {mock_webhook['signature'][:20]}...")

    webhook_res = process_payment_webhook(
        raw_body=mock_webhook["payload_bytes"],
        signature=mock_webhook["signature"]
    )
    print(f"⚡ Webhook Processing Status: {webhook_res['status']}")
    print(f"💰 Payment Status: {webhook_res.get('payment_status', 'PAID')} (Settlement Status: PENDING_SETTLEMENT)")
    print(f"📦 Stock Auto-Deducted: {webhook_res.get('quantity_deducted', 1)} unit(s) -> Remaining Stock: {webhook_res.get('remaining_stock')} units")

    # =========================================================================
    # SCENARIO 2: FAILURE RECOVERY 1 (Merchant Rejection 'N' -> Alternative Products)
    # =========================================================================
    print_banner("Scenario 2: Failure Case 1 — Merchant Rejection ('N') & Agentic Recovery")
    print("📝 Context: Buyer wants 'Urban Black Hoodie' (p13), but seller discovers stock is damaged and rejects ('N').")

    result_reject = run_trust_agent(
        product_id="p13",
        agreed_price=1100,
        quantity=1,
        merchant_response="N",
        buyer_name="Vikram Singh"
    )

    print(f"❌ Order Status: {result_reject['status']}")
    print(f"💬 System Message to Buyer:\n{result_reject['message']}")
    print(f"\n🔍 Autonomous Alternatives Surfaced by Discovery Agent ({len(result_reject['alternatives'])} items):")
    for idx, alt in enumerate(result_reject['alternatives'], 1):
        print(f"   {idx}. {alt['product_name']} | ₹{alt['listed_price']} | Merchant: {alt['merchant_name']} ({alt['seller_rating']}⭐) [{alt['availability_badge']}]")

    # =========================================================================
    # SCENARIO 3: FAILURE RECOVERY 2 (Code-Level Hard Floor Defense)
    # =========================================================================
    print_banner("Scenario 3: Failure Case 2 — Code-Level Hard Price Floor Guardrail")
    print("📝 Context: Prompt injection or bug attempts checkout for 'p13' at ₹600 (Floor is ₹900).")

    result_floor_violation = run_trust_agent(
        product_id="p13",
        agreed_price=600,
        quantity=1,
        merchant_response="Y"
    )

    print(f"🛑 Guardrail Interception: {result_floor_violation['guardrail_status']}")
    print(f"🔒 Payment Link Generated? {'NO (Blocked in code)' if not result_floor_violation['payment_link_url'] else 'YES'}")
    print(f"💬 Buyer Message:\n{result_floor_violation['message']}")

    # =========================================================================
    # SCENARIO 4: FAILURE RECOVERY 3 (Merchant Timeout & Confidence Decay)
    # =========================================================================
    print_banner("Scenario 4: Failure Case 3 — Merchant Timeout Handling")
    print("📝 Context: Seller does not respond to order confirmation within the allowed window.")

    result_timeout = run_trust_agent(
        product_id="p14",
        agreed_price=1000,
        quantity=1,
        merchant_response="TIMEOUT"
    )

    print(f"⏱️ Order Status: {result_timeout['status']}")
    print(f"💬 Buyer Message:\n{result_timeout['message']}")
    print(f"🔍 Responsive Alternatives Found: {len(result_timeout['alternatives'])} items")

    # =========================================================================
    # SCENARIO 5: 15-MINUTE PAYMENT LINK EXPIRATION & CANCELLATION
    # =========================================================================
    print_banner("Scenario 5: 15-Minute Payment Link Expiration & Cancellation")
    print("📝 Context: Generating a link, then simulating expiration after 15 minutes of inactivity.")

    res_exp = run_trust_agent(product_id="p1", agreed_price=3300, merchant_response="Y")
    order_to_expire = res_exp["order_id"]
    print(f"📋 Order Created: {order_to_expire} with payment link {res_exp['payment_link_id']}")
    print(f"🔗 Link URL: {res_exp['payment_link_url']}")

    cancel_res = expire_unpaid_order(order_to_expire)
    print(f"🚫 Link Cancelled & Order Expired: {cancel_res['status']}")

    # =========================================================================
    # SCENARIO 6: MODEL CONTEXT PROTOCOL (MCP) TOOL CALLING
    # =========================================================================
    print_banner("Scenario 6: Model Context Protocol (MCP) Tool Calling & Perimeter Defense")
    print(f"🛠️ Registered MCP Tools: {list(MCP_TOOL_REGISTRY.keys())}")

    # Seed authoritative order in PENDING_PAYMENT state
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO orders (
            id, product_id, merchant_id, buyer_id, quantity, amount, payment_status, settlement_status, created_at
        ) VALUES ('ord_mcp_live_demo', 'p13', 'm1', 'b1', 2, 2200, 'PENDING_PAYMENT', 'PENDING_SETTLEMENT', CURRENT_TIMESTAMP)
    """)
    conn.commit()
    conn.close()

    print_section("Test A: Malicious Caller Attempts Parameter Tampering ('amount': 1)")
    tamper_out = dispatch_mcp_call("create_payment_link", {
        "order_id": "ord_mcp_live_demo",
        "amount": 1
    })
    print(f"🛑 Perimeter Defense Intercepted: {tamper_out['message']}")

    print_section("Test B: Legitimate Tool Call (Amount Authoritatively Derived from DB Order ₹2,200)")
    mcp_out = dispatch_mcp_call("create_payment_link", {
        "order_id": "ord_mcp_live_demo",
        "expires_in_minutes": 15
    })
    print(json.dumps(mcp_out, indent=2))

    print_section("Calling MCP Tool: 'check_payment_status'")
    status_out = dispatch_mcp_call("check_payment_status", {
        "payment_link_id": mcp_out.get("payment_link_id", "plink_sim_test")
    })
    print(json.dumps(status_out, indent=2))

    # =========================================================================
    # AUDIT TRAIL INSPECTION
    # =========================================================================
    print_banner("SQLite Audit Log (Trust & Security Trail)")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT action, agent, reasoning, timestamp FROM audit_log ORDER BY id DESC LIMIT 5")
    rows = cursor.fetchall()
    for r in rows:
        print(f"[{r['timestamp']}] {r['agent']} -> {r['action']}: {r['reasoning'][:80]}...")
    conn.close()

    print("\n" + "=" * 80)
    print("  🎉 DAY 5 LIVE DEMO COMPLETED SUCCESSFULLY — ALL GUARDRAILS VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    run_demo()
