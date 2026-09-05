with open("main.py", "r") as f:
    content = f.read()

route = """
class SetStockRequest(BaseModel):
    new_stock: int

@app.post("/api/catalog/products/{product_id}/set_stock")
def set_product_stock(product_id: str, req: SetStockRequest):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE products SET stock_quantity = ? WHERE id = ?", (req.new_stock, product_id))
        conn.commit()
        conn.close()
        return {"success": True, "product_id": product_id, "new_stock": req.new_stock}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
"""

# Insert before the last line
content = content.replace("if __name__ == \"__main__\":", route + "\nif __name__ == \"__main__\":")

with open("main.py", "w") as f:
    f.write(content)
print("Added set_stock route")
