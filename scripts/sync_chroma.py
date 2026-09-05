import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import get_db_connection
from core.chroma_store import add_product_to_vector_store

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("SELECT id, product_name, category, description, search_tags_json FROM products")
rows = cursor.fetchall()

print(f"Found {len(rows)} products to sync to ChromaDB.")

count = 0
for row in rows:
    try:
        add_product_to_vector_store(
            product_id=row["id"],
            name=row["product_name"],
            category=row["category"],
            description=row["description"],
            search_tags=row["search_tags_json"] or "[]"
        )
        count += 1
        if count % 50 == 0:
            print(f"Synced {count}/{len(rows)}")
    except Exception as e:
        print(f"Failed to sync {row['id']}: {e}")

print("✅ ChromaDB sync complete.")
