import json
import random

# Base Merchants
merchants = [
    # SNEAKERS
    {"id": "m1", "name": "Sneaker Bhai", "category": "Footwear > Sneakers"},
    {"id": "m4", "name": "Kicks Delhi", "category": "Footwear > Sneakers"},
    {"id": "m5", "name": "Sole Mates", "category": "Footwear > Sneakers"},
    {"id": "m6", "name": "Urban Kicks", "category": "Footwear > Sneakers"},
    {"id": "m7", "name": "The Sneaker Shop", "category": "Footwear > Sneakers"},
    
    # ETHNIC
    {"id": "m2", "name": "Saree Palace", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m8", "name": "Ethnic Vogue", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m9", "name": "Desi Threads", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m10", "name": "Saree Symphony", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m11", "name": "Ethnic Elegance", "category": "Clothing > Womenswear > Ethnic"},
    
    # STREETWEAR
    {"id": "m3", "name": "Streetwear Hub", "category": "Clothing > Menswear"},
    {"id": "m12", "name": "Hypebeast India", "category": "Clothing > Menswear"},
    {"id": "m13", "name": "Street Style Co", "category": "Clothing > Menswear"},
    {"id": "m14", "name": "Metro Menswear", "category": "Clothing > Menswear"},
    {"id": "m15", "name": "The Hype Store", "category": "Clothing > Menswear"},

    # EXTRA SNEAKERS
    {"id": "m16", "name": "Sneaker Central", "category": "Footwear > Sneakers"},
    {"id": "m17", "name": "Kicksville", "category": "Footwear > Sneakers"},
    {"id": "m18", "name": "Lace Up", "category": "Footwear > Sneakers"},
    {"id": "m19", "name": "Sole Search", "category": "Footwear > Sneakers"},
    {"id": "m20", "name": "Sneaker Society", "category": "Footwear > Sneakers"},

    # EXTRA ETHNIC
    {"id": "m21", "name": "Saree Mandir", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m22", "name": "Vastra", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m23", "name": "Ethnic Charm", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m24", "name": "Indian Weaves", "category": "Clothing > Womenswear > Ethnic"},
    {"id": "m25", "name": "Silk Story", "category": "Clothing > Womenswear > Ethnic"},

    # EXTRA STREETWEAR
    {"id": "m26", "name": "Street Pulse", "category": "Clothing > Menswear"},
    {"id": "m27", "name": "Urban Drops", "category": "Clothing > Menswear"},
    {"id": "m28", "name": "Hype Central", "category": "Clothing > Menswear"},
    {"id": "m29", "name": "The Street Code", "category": "Clothing > Menswear"},
    {"id": "m30", "name": "City Fits", "category": "Clothing > Menswear"}
]

# Generate detailed merchants
seed_merchants = []
for m in merchants:
    seed_merchants.append({
        "id": m["id"],
        "name": m["name"],
        "phone_number": f"+919{random.randint(100000000, 999999999)}",
        "reliability_score": round(random.uniform(4.0, 5.0), 1),
        "api_key": f"merchant_key_{m['id']}",
        "razorpay_account_id": f"acc_test_{m['id']}",
        "merchant_dna_json": json.dumps({"flexibility": random.choice(["Flexible", "Strict", "Very Flexible", "Moderate"]), "price_tier": "Mid-Range", "primary_category": m["category"], "avg_discount_pct": random.randint(10, 25)})
    })

# Curated Product Mapping
curated_products = [
    # SNEAKERS
    {"name": "Nike Air Force 1 White", "image": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Air Jordan 1 High Red", "image": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Yeezy Boost 350 V2", "image": "https://images.unsplash.com/photo-1515955656352-a1fa3ffcd111?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Nike Dunk Low Retro", "image": "https://images.unsplash.com/photo-1579338559194-a162d19bf842?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Adidas Ultraboost Light", "image": "https://images.unsplash.com/photo-1608231387042-66d1773070a5?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Puma RS-X Triple White", "image": "https://images.unsplash.com/photo-1600185365483-26d7a4cc7519?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "New Balance 550 Vintage", "image": "https://images.unsplash.com/photo-1551107696-a4b0c5a0d9a2?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Vans Old Skool Black", "image": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Converse Chuck 70 High", "image": "https://images.unsplash.com/photo-1605348532760-6753d2c43329?w=600&q=80", "cat": "Footwear > Sneakers"},
    {"name": "Reebok Club C 85", "image": "https://images.unsplash.com/photo-1612821745145-c1e550e50882?w=600&q=80", "cat": "Footwear > Sneakers"},
    
    # ETHNIC
    {"name": "Kanjivaram Red Silk Saree", "image": "https://images.unsplash.com/photo-1610030469983-98e550d61dc0?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Banarasi Blue Silk Saree", "image": "https://images.unsplash.com/photo-1583391733958-b6107a6be32a?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Chanderi Cotton Pink Saree", "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Yellow Floral Chiffon Saree", "image": "https://images.unsplash.com/photo-1550614000-4b9e78ea38a3?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Georgette Party Wear Saree", "image": "https://images.unsplash.com/photo-1615886915124-73347b7190f8?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Embroidered Silk Lehenga", "image": "https://images.unsplash.com/photo-1598539962534-1c4b786419dc?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Cotton Printed Anarkali Kurti", "image": "https://images.unsplash.com/photo-1583391733958-b6107a6be32a?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Pastel Designer Lehenga", "image": "https://images.unsplash.com/photo-1610030469983-98e550d61dc0?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "Bridal Red Velvet Lehenga", "image": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    {"name": "White Net Threadwork Saree", "image": "https://images.unsplash.com/photo-1550614000-4b9e78ea38a3?w=600&q=80", "cat": "Clothing > Womenswear > Ethnic"},
    
    # STREETWEAR
    {"name": "Heavyweight Black Hoodie", "image": "https://images.unsplash.com/photo-1556821840-3a63f95609a7?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Oversized Graphic T-Shirt", "image": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Vintage Wash Grey Hoodie", "image": "https://images.unsplash.com/photo-1516257984-b1b4d707412e?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Olive Tactical Cargo Pants", "image": "https://images.unsplash.com/photo-1552374196-1ab2a1c593e8?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Streetwear Varsity Jacket", "image": "https://images.unsplash.com/photo-1617137968427-85924c800a22?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Distressed Denim Jeans", "image": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Boxy Fit Plain White Tee", "image": "https://images.unsplash.com/photo-1529374255404-311a2a4f1fd9?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Parachute Pants Black", "image": "https://images.unsplash.com/photo-1584865288642-42078afe6942?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Oversized Flannel Shirt", "image": "https://images.unsplash.com/photo-1596755094514-f87e32f85e2c?w=600&q=80", "cat": "Clothing > Menswear"},
    {"name": "Utility Techwear Vest", "image": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=600&q=80", "cat": "Clothing > Menswear"}
]

seed_products = []
p_id_counter = 1

# Generate product catalog
# We have 10 specific curated products per category.
# To make 5 merchants compete, each merchant will list all 10 products!
# This gives us 50 products per category (total 150), but they are exactly the same product names/images, just competing on price/rating!

for p in curated_products:
    cat = p["cat"]
    # Find the 5 merchants for this category
    cat_merchants = [m["id"] for m in merchants if m["category"] == cat]
    
    for m_id in cat_merchants:
        listed_price = random.randint(1500, 5000)
        floor_price = listed_price - random.randint(300, 800)
        
        seed_products.append({
            "id": f"p_quality_{p_id_counter}",
            "merchant_id": m_id,
            "product_name": p["name"],
            "category": cat,
            "search_tags": ["fashion", cat.split(" > ")[-1].lower()],
            "listed_price": listed_price,
            "floor_price": floor_price,
            "stock_quantity": random.randint(5, 50),
            "attributes_json": json.dumps({"Color": "Multi", "Size": "M, L, XL"}),
            "image_path": p["image"]
        })
        p_id_counter += 1

output = {
    "merchants": seed_merchants,
    "buyers": [
        {"id": "b1", "phone_number": "+919876543210", "buyer_trust_score": 9.5, "return_rate": 0.05}
    ],
    "products": seed_products
}

with open("data/seed_data.json", "w") as f:
    json.dump(output, f, indent=2)

app_m_list = [{"id": m["id"], "name": m["name"]} for m in seed_merchants]
with open("app_merchants_curated.json", "w") as f:
    json.dump(app_m_list, f, indent=2)

print("Generated PERFECT curated seed data!")
