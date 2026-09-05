with open("main.py", "r") as f:
    content = f.read()

route = """
class StockUpdateRequest(BaseModel):
    units_sold: int

@app.post("/api/catalog/products/{product_id}/reduce_stock")
def reduce_product_stock(product_id: str, req: StockUpdateRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stock_quantity FROM products WHERE id = ?", (product_id,))
        row = cursor.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "Product not found"})
        
        new_stock = max(0, row["stock_quantity"] - req.units_sold)
        cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (new_stock, product_id))
        conn.commit()
        conn.close()
        return {"success": True, "product_id": product_id, "new_stock": new_stock}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
"""

# Insert before the last line if possible, or just append it right before the "__main__" block
if "if __name__ == \"__main__\":" in content:
    content = content.replace("if __name__ == \"__main__\":", route + "\nif __name__ == \"__main__\":")
else:
    content += "\n" + route

with open("main.py", "w") as f:
    f.write(content)
print("Added stock route")
