"""
MerchantMesh - Quick Endpoint Diagnostic Script
Run with: python test_endpoints.py (when FastAPI server is running on port 8000)
"""


import requests

BASE_URL = "http://localhost:8000"

print("🔍 1. Testing Health Check (GET /)...")
try:
    res = requests.get(f"{BASE_URL}/")
    print(f"   Status: {res.status_code} | Response: {res.json()}")
except Exception as e:
    print(f"   Error: {e}")

print("\n📦 2. Testing Dynamic Merchants (GET /api/merchants)...")
try:
    res = requests.get(f"{BASE_URL}/api/merchants")
    print(f"   Status: {res.status_code} | Merchants Count: {len(res.json().get('merchants', []))}")
except Exception as e:
    print(f"   Error: {e}")

print("\n🏷️ 3. Testing Catalog Bot Parsing (POST /api/catalog/parse)...")
try:
    res = requests.post(f"{BASE_URL}/api/catalog/parse", json={
        "message": "New black oversized hoodie Rs 1500, minimum floor 1100, 15 pieces in stock",
        "merchant_id": "m1"
    })
    print(f"   Status: {res.status_code} | Product ID: {res.json().get('product_id')}")
    print(f"   Extracted: {res.json().get('parsed', {}).get('product_name')} @ ₹{res.json().get('parsed', {}).get('listed_price')}")
except Exception as e:
    print(f"   Error: {e}")

print("\n🛍️ 4. Testing Buyer Discovery (POST /api/buyer/chat)...")
try:
    res = requests.post(f"{BASE_URL}/api/buyer/chat", json={
        "query": "black hoodie under 1500",
        "buyer_id": "b1"
    })
    print(f"   Status: {res.status_code} | Discovered: {len(res.json().get('products', []))} products")
except Exception as e:
    print(f"   Error: {e}")

print("\n🤝 5. Testing Negotiation (POST /api/negotiate)...")
try:
    res = requests.post(f"{BASE_URL}/api/negotiate", json={
        "product_id": "p13",
        "buyer_target_price": 950,
        "buyer_max_budget": 1200,
        "quantity": 1,
        "buyer_id": "b1"
    })
    print(f"   Status: {res.status_code} | Negotiation Outcome: {res.json().get('status')} @ ₹{res.json().get('final_price')}")
except Exception as e:
    print(f"   Error: {e}")

print("\n📜 6. Testing UAP Agent Discovery Manifest (GET /.well-known/agent.json)...")
try:
    res = requests.get(f"{BASE_URL}/.well-known/agent.json")
    print(f"   Status: {res.status_code} | Protocol: {res.json().get('protocol')} | Capabilities: {res.json().get('capabilities')}")
except Exception as e:
    print(f"   Error: {e}")

print("\n✅ All diagnostic endpoint tests completed.")

