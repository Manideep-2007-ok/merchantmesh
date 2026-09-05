import json
import sqlite3

from core.chroma_store import add_product_to_vector_store


def main():
    conn = sqlite3.connect("data/merchantmesh.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE is_prohibited = 0 AND stock_quantity > 0")
    rows = cursor.fetchall()
    
    count = 0
    for r in rows:
        tags = json.loads(r["search_tags_json"]) if r["search_tags_json"] else []
        cat = r["category"] or ""
        name = r["product_name"] or ""
        text = f"{name} {cat} {' '.join(tags)}".lower()
        
        metadata = {
            "merchant_id": r["merchant_id"],
            "category": cat,
            "listed_price": r["listed_price"],
            "floor_price": r["floor_price"] or r["listed_price"],
            "stock_quantity": r["stock_quantity"]
        }
        add_product_to_vector_store(r["id"], text, metadata)
        count += 1
        
    print(f"Successfully vectorized and backfilled {count} products into ChromaDB!")

if __name__ == "__main__":
    main()
