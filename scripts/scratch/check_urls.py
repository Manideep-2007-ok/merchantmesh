import sqlite3
import urllib.request

conn = sqlite3.connect("data/merchantmesh.db")
cursor = conn.cursor()
cursor.execute("SELECT image_path FROM products")
for row in cursor.fetchall():
    url = row[0]
    if url:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            res = urllib.request.urlopen(req)
            if res.status != 200:
                print(f"FAILED: {url} (Status: {res.status})")
        except Exception as e:
            print(f"ERROR: {url} - {e}")
print("Done checking.")
