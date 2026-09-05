"""
MerchantMesh - Multi-Agent Negotiation Demo CLI
Demonstrates:
1. Two-Sided Multi-Turn Haggling (Hinglish/English conversational personas)
2. Strict Code-Level Hard Price Floor Guardrail Protection
3. Dynamic Seller Styles from Merchant DNA (Generous vs Firm)
4. Bulk / Bundle Volume Discount Negotiation (Quantity > 1)
5. Adversarial Prompt Injection Defense
"""

import json
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.negotiation_agent import run_negotiation
from data.database import get_db_connection, init_db
from scripts.seed_db import seed_from_json


def print_turn(turn: dict):
    speaker = turn["speaker"]
    price = turn["proposed_price"]
    msg = turn["message"]
    reasoning = turn["internal_reasoning"]
    status = turn.get("guardrail_status", "PASSED")

    if speaker == "BUYER":
        icon = "🛍️  BUYER AGENT"
        prefix = "   [Buyer Bid]"
        color = "\033[94m" # Blue
    elif speaker == "SELLER":
        icon = "🏪 SELLER AGENT"
        prefix = "   [Seller Ask]"
        color = "\033[92m" # Green
    else:
        icon = "⚙️  SYSTEM"
        prefix = "   [System]"
        color = "\033[93m" # Yellow
    
    reset = "\033[0m"
    
    print(f"\n{color}{icon} — Turn {turn['turn_number']} ({turn['action']}){reset}")
    print(f"{prefix} Proposed Price: ₹{price:,} | Guardrail: {status}")
    print(f"   💬 Message: \"{msg}\"")
    print(f"   🧠 Internal Reasoning: {reasoning}")


def run_scenario(title: str, description: str, product_id: str, target_price: int, max_budget: int, quantity: int = 1):
    print("\n" + "=" * 80)
    print(f"🔥 SCENARIO: {title}")
    print(f"ℹ️  {description}")
    print("=" * 80)

    # Fetch product info from DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.product_name, p.listed_price, p.floor_price, m.name as merchant_name, m.merchant_dna_json
        FROM products p JOIN merchants m ON p.merchant_id = m.id WHERE p.id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        dna = json.loads(row["merchant_dna_json"]) if row["merchant_dna_json"] else {}
        print(f"📦 Product: {row['product_name']} (Qty: {quantity})")
        print(f"🏪 Merchant: {row['merchant_name']} (Flexibility: {dna.get('flexibility', 'Flexible')})")
        print(f"💵 Unit Listed: ₹{row['listed_price']:,} | Unit Floor (Secret): ₹{row['floor_price']:,}")
        print(f"🎯 Buyer Target: ₹{target_price:,} | Max Budget: ₹{max_budget:,}")
        print("-" * 80)

    result = run_negotiation(
        product_id=product_id,
        buyer_target_price=target_price,
        buyer_max_budget=max_budget,
        quantity=quantity,
        buyer_id="b1"
    )

    for t in result.get("turns", []):
        print_turn(t)
        time.sleep(0.3)

    print("\n" + "-" * 80)
    print(f"🏁 NEGOTIATION OUTCOME: {result['status']}")
    if result.get("final_price"):
        print(f"💰 Final Settlement Price: ₹{result['final_price']:,} for {quantity} item(s)")
        print(f"💸 Total Buyer Savings: ₹{result['savings_amount']:,} ({result['savings_pct']}% OFF)")
    print(f"📜 Audit Reasoning: {result['audit_reasoning']}")
    print("-" * 80)


def main():
    print("🚀 Initializing MerchantMesh Database & Seeding Fresh Catalog...")
    init_db()
    seed_from_json()

    # Scenario 1: Standard Successful 3-Turn Negotiation
    run_scenario(
        title="1. Standard Multi-Turn Negotiation (Hoodie Deal)",
        description="Buyer searches for Urban Black Hoodie (Listed ₹1,500, Secret Floor ₹900). Offers ₹950. Seller counters and they meet at a win-win price.",
        product_id="p13",
        target_price=950,
        max_budget=1200,
        quantity=1
    )

    # Scenario 2: Hard Floor Price Guardrail Protection (Lowball Defense)
    run_scenario(
        title="2. Hard Floor Price Defense (Lowball Attempt)",
        description="Buyer lowballs at ₹500 when merchant's floor is ₹900. Code-level guardrail enforces minimum margin.",
        product_id="p13",
        target_price=500,
        max_budget=600,
        quantity=1
    )

    # Scenario 3: Merchant DNA Behavioral Comparison (Firm Seller)
    run_scenario(
        title="3. Firm Merchant Style (Sneakers)",
        description="Negotiating with a 'Firm' style merchant (Listed ₹3,999, Floor ₹3,499). Seller holds firm and concedes slowly.",
        product_id="p1",
        target_price=3200,
        max_budget=3700,
        quantity=1
    )

    # Scenario 4: Bulk / Bundle Deal (Quantity = 3)
    run_scenario(
        title="4. Bulk / Bundle Deal (3x Hoodies with Volume Discount)",
        description="Buyer purchases 3 pieces. The system auto-calculates volume floor discount and negotiates wholesale pricing.",
        product_id="p13",
        target_price=2700,
        max_budget=3600,
        quantity=3
    )

    # Scenario 5: Pan-India Universal Language Mirroring (Bengaluru / Chennai Buyer)
    run_scenario(
        title="5. Pan-India Language Mirroring (Bengaluru / Chennai Buyer in English)",
        description="Buyer from South India negotiates in conversational Indian English ('Bro, make it 3400 for UPI'). Seller agent detects language and mirrors seamlessly without Hindi bias.",
        product_id="p1",
        target_price=3300,
        max_budget=3600,
        quantity=1
    )


if __name__ == "__main__":
    main()
