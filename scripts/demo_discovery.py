"""
MerchantMesh - Interactive Discovery Agent Demo CLI
Allows testing sample buyer queries (Hinglish/English) against the seeded catalog
and displays the Top 3 Personal Shopper recommendations with explainability badges.
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.discovery_agent import run_discovery_agent
from data.database import init_db
from scripts.seed_db import seed_from_json

DEMO_QUERIES = [
    "kala hoodie under 1200",
    "Diwali gift for mom under 3000",
    "comfortable running shoes size 9 under 4000",
    "saste me stylish sneakers",
    "hoodie under 200" # Demonstrates Budget Cap Alert
]


def print_discovery_results(query: str):
    print("\n" + "=" * 70)
    print(f"🛍️  BUYER QUERY: '{query}'")
    print("=" * 70)
    
    res = run_discovery_agent(query, buyer_id="b1")
    
    print(f"📌 Status: {res['status']}")
    print(f"💬 Agent Message: {res['message']}")
    
    parsed = res.get("parsed_query")
    if parsed:
        print("\n🧠 Extracted Understanding:")
        print(f"   • Translated Intent: {parsed.get('translated_query')}")
        print(f"   • Inferred Category: {parsed.get('category')}")
        print(f"   • Max Budget: ₹{parsed.get('max_budget')}" if parsed.get('max_budget') else "   • Max Budget: Flexible")
        print(f"   • Price Sensitivity: {parsed.get('price_sensitivity')}")
        print(f"   • Occasion/Context: {parsed.get('recipient_or_occasion') or 'General'}")

    if res.get("status") == "BUDGET_TOO_LOW":
        print(f"\n💡 Suggested Negotiation Budget: ₹{res.get('suggested_budget'):,}")
        closest = res.get("closest_match")
        if closest:
            print(f"   Closest Item: {closest['product_name']} (Listed: ₹{closest['listed_price']:,})")
        print("\n🔍 Nearest Matching Products in Catalog (Require Budget Adjustment):")
        for p in res.get("ranked_products", []):
            print(f"   • {p['product_name']} — Listed: ₹{p['listed_price']:,} | Seller: {p['merchant_name']} ({p['seller_rating']}⭐)")
    else:
        ranked = res.get("ranked_products", [])
        if ranked:
            print(f"\n⭐ TOP {len(ranked)} PERSONAL SHOPPER RECOMMENDATIONS:")
            for p in ranked:
                print(f"\n  #{p.get('rank', '-')} {p['product_name']}")
                print(f"     🏪 Merchant: {p.get('merchant_name')} | Seller Rating: {p.get('seller_rating')} ⭐")
                print(f"     💵 Listed: ₹{p.get('listed_price'):,} | Hidden Floor: ₹{p.get('floor_price'):,}")
                print(f"     🏷️  Status: {p.get('availability_badge')}")
                print(f"     🤝 Negotiation: {p.get('negotiation_hint')}")
                print(f"     💡 Why Recommended: {p.get('why_recommended')}")


def main():
    init_db()
    seed_from_json()
    
    if len(sys.argv) > 1:
        custom_query = " ".join(sys.argv[1:])
        print_discovery_results(custom_query)
    else:
        for q in DEMO_QUERIES:
            print_discovery_results(q)


if __name__ == "__main__":
    main()
