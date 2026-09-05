import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.database import get_db_connection
from core.chroma_store import add_product_to_vector_store

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT id, product_name, category, search_tags_json FROM products")
rows = cursor.fetchall()

print(f"Found {len(rows)} products to sync to ChromaDB.")

count = 0
for row in rows:
    try:
        search_tags = json.loads(row["search_tags_json"] or "[]")
        tags_str = ", ".join(search_tags)
        text = f"{row['product_name']} in {row['category']}. Keywords: {tags_str}"
        add_product_to_vector_store(
            product_id=row["id"],
            text=text,
            metadata={"category": row["category"], "product_name": row["product_name"]}
        )
        count += 1
        if count % 50 == 0:
            print(f"Synced {count}/{len(rows)}")
    except Exception as e:
        print(f"Failed to sync {row['id']}: {e}")

print("✅ ChromaDB sync complete.")
