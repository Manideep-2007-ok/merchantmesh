with open('data/database.py', 'r') as f:
    c = f.read()

# Add the missing column creation logic right before creating the index
fix = """
    if "session_id" not in neg_cols:
        cursor.execute("ALTER TABLE negotiations ADD COLUMN session_id TEXT")
        
    if "merchant_id" not in neg_cols:
        cursor.execute("ALTER TABLE negotiations ADD COLUMN merchant_id TEXT")
"""

c = c.replace('    if "session_id" not in neg_cols:\n        cursor.execute("ALTER TABLE negotiations ADD COLUMN session_id TEXT")', fix)

with open('data/database.py', 'w') as f:
    f.write(c)
