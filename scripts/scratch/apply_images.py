import json

mapping_path = "/home/manideep/.gemini/antigravity/brain/60d6a3a2-bc46-47a5-8065-27380dc79840/scratch/image_mapping.json"
with open(mapping_path, "r") as f:
    mapping = json.load(f)

img_dict = {item["name"]: item["url"] for item in mapping if item["url"].strip()}

with open("data/seed_data.json", "r") as f:
    data = json.load(f)

updated = 0
for p in data["products"]:
    if p["product_name"] in img_dict:
        p["image_path"] = img_dict[p["product_name"]]
        updated += 1

with open("data/seed_data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Updated {updated} products with correct images in seed_data.json")
