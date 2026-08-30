import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from data.database import get_db_connection


def seed_from_json():
    """Reads seed data from JSON and inserts it into the database cleanly."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "seed_data.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 1. Insert Merchants
        for m in data.get("merchants", []):
            cursor.execute(
                """
                INSERT INTO merchants (id, name, phone_number, reliability_score, merchant_dna_json, api_key, razorpay_account_id) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    phone_number = excluded.phone_number,
                    reliability_score = excluded.reliability_score,
                    merchant_dna_json = excluded.merchant_dna_json,
                    api_key = COALESCE(excluded.api_key, merchants.api_key),
                    razorpay_account_id = COALESCE(excluded.razorpay_account_id, merchants.razorpay_account_id)
                """,
                (m["id"], m["name"], m["phone_number"], m["reliability_score"], m["merchant_dna_json"], m.get("api_key", f"merchant_key_{m['id']}"), m.get("razorpay_account_id", f"acc_test_{m['id']}"))
            )

        # 2. Insert Buyers
        for b in data.get("buyers", []):
            cursor.execute(
                """
                INSERT INTO buyers (id, phone_number, buyer_trust_score, return_rate) 
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    phone_number = excluded.phone_number,
                    buyer_trust_score = excluded.buyer_trust_score,
                    return_rate = excluded.return_rate
                """,
                (b["id"], b["phone_number"], b["buyer_trust_score"], b["return_rate"])
            )

        # 3. Insert Products (Standardized to UTC)
        now = datetime.now(timezone.utc)
        for p in data.get("products", []):
            target_dt = now - timedelta(days=p.get("days_old", 0))
            target_str = target_dt.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO products 
                (id, merchant_id, product_name, category, search_tags_json, sizes_json, listed_price, floor_price, stock_quantity, image_path, is_prohibited, confidence_score, created_at, updated_at, stock_last_confirmed_at) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    merchant_id = excluded.merchant_id,
                    product_name = excluded.product_name,
                    category = excluded.category,
                    search_tags_json = excluded.search_tags_json,
                    sizes_json = excluded.sizes_json,
                    listed_price = excluded.listed_price,
                    floor_price = excluded.floor_price,
                    stock_quantity = excluded.stock_quantity,
                    image_path = excluded.image_path,
                    is_prohibited = excluded.is_prohibited,
                    confidence_score = excluded.confidence_score
            ''', (
                p["id"], p["merchant_id"], p["product_name"], p["category"], 
                json.dumps(p.get("search_tags", [])), json.dumps(p.get("sizes", [])), 
                p["listed_price"], p["floor_price"], p["stock_quantity"], p.get("image_path"), 
                p.get("is_prohibited", 0), p.get("confidence_score", 100.0), 
                target_str, target_str, target_str
            ))

        conn.commit()
    finally:
        conn.close()
    print(f"✅ Database seeded successfully with {len(data.get('products', []))} products from data/seed_data.json!")

if __name__ == "__main__":
    seed_from_json()
