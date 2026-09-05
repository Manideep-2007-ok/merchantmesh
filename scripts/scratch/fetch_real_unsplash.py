import json
import urllib.request

queries = [
    "Nike Air Force 1 White", "Air Jordan 1 High Red", "Yeezy Boost 350", "Nike Dunk Low", "Adidas Ultraboost",
    "Puma RS", "New Balance 550", "Vans Old Skool", "Converse Chuck", "Reebok Club",
    "Red Silk Saree", "Blue Silk Saree", "Pink Saree", "Yellow Chiffon Saree", "Georgette Saree",
    "Silk Lehenga", "Anarkali Kurti", "Designer Lehenga", "Red Velvet Lehenga", "White Net Saree",
    "Black Hoodie", "Graphic T-Shirt", "Grey Hoodie", "Cargo Pants", "Varsity Jacket",
    "Denim Jeans", "White Tee", "Parachute Pants", "Flannel Shirt", "Techwear Vest"
]

results = {}
for q in queries:
    try:
        url = "https://unsplash.com/napi/search/photos?query=" + urllib.parse.quote(q) + "&per_page=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data['results']:
                results[q] = data['results'][0]['urls']['regular']
            else:
                results[q] = "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80" # Fallback
    except Exception as e:
        print(f"Failed {q}: {e}")
        results[q] = "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80" # Fallback

with open("real_unsplash_images.json", "w") as f:
    json.dump(results, f, indent=2)

print("Fetched real URLs!")
