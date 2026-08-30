import os

import chromadb

# Persistent local ChromaDB
CHROMA_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "chroma_db")

# Initialize client
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)

# Get or create the collection for products
product_collection = chroma_client.get_or_create_collection(name="products")

def add_product_to_vector_store(product_id: str, text: str, metadata: dict):
    """Adds a product vector to ChromaDB."""
    try:
        product_collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[product_id]
        )
    except Exception as e:
        print(f"⚠️ ChromaDB Error adding product: {e}")

def semantic_search(query: str, n_results: int = 15) -> list:
    """Searches ChromaDB and returns matching product IDs."""
    try:
        results = product_collection.query(
            query_texts=[query],
            n_results=n_results
        )
        if results and "ids" in results and results["ids"]:
            return results["ids"][0]
        return []
    except Exception as e:
        print(f"⚠️ ChromaDB Error during search: {e}")
        return []

