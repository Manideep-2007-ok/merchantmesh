import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_gen import create_product_card
from core.parser import parse_product

TEST_CASES = [
    {
        "name": "1. Saree with Hindi text",
        "caption": "Naya silk saree collection. Price 2500, but 2000 se neeche nahi dena. 5 bache hain.",
        "image_path": None
    },
    {
        "name": "2. Hoodie with Hinglish",
        "caption": "Black oversized hoodie 🔥 bhai check kar lo, 1500 MRP, last price 1200. Sizes S, M, L available hai.",
        "image_path": "data/test_images/hoodie.jpg"
    },
    {
        "name": "3. Shoes with English caption",
        "caption": "Premium running shoes. Best quality. DM for price.",
        "image_path": "data/test_images/shoes.jpg"
    },
    {
        "name": "4. Product with no price mentioned",
        "caption": "Awesome new smartwatch arrived today. Only 2 left in stock!",
        "image_path": "data/test_images/no_price.jpg"
    },
    {
        "name": "5. Blurry photo",
        "caption": "Handmade leather wallet.",
        "image_path": "data/test_images/blurry.jpg"
    },
    {
        "name": "6. Instagram screenshot (Bonus)",
        "caption": "", # Assuming IG screenshot has text in it. We will simulate with an image if possible, but testing caption empty logic
        "image_path": "data/test_images/ig_screenshot.jpg"
    },
    {
        "name": "7. Guardrails (Prohibited Item)",
        "caption": "Selling imported switchblade knife. Very sharp. DM for price.",
        "image_path": None
    }
]

def run_tests():
    print("🚀 Starting Parser Tests...\n")
    os.makedirs("data/output", exist_ok=True)
    
    for idx, tc in enumerate(TEST_CASES):
        print(f"--- TEST {tc['name']} ---")
        try:
            # We skip image passing if image doesn't exist to avoid errors in this test
            img = tc["image_path"] if tc["image_path"] and os.path.exists(tc["image_path"]) else None
            result = parse_product(caption=tc["caption"], image_path=img)
            
            print(f"Product Name: {result.product_name}")
            print(f"Category: {result.category}")
            print(f"Search Tags: {result.search_tags}")
            print(f"Listed Price: {result.listed_price}")
            print(f"Floor Price: {result.floor_price}")
            print(f"Stock: {result.stock_quantity}")
            print(f"Missing: {result.missing_information}")
            print(f"Discrepancies: {result.discrepancies}")
            print(f"Is Prohibited: {result.is_prohibited}")
            if result.is_prohibited:
                print(f"Prohibited Reason: {result.prohibited_reason}")
            print(f"Needs Clarification: {result.clarification_needed}")
            if result.clarification_needed:
                print(f"Vendor Bot Message: {result.clarification_message}")
            print(f"\nWhatsApp Status:\n{result.whatsapp_status}")
            print(f"\nIG Caption:\n{result.instagram_caption}\n")
            
            if img:
                out_path = f"data/output/card_{idx+1}.jpg"
                create_product_card(img, result.product_name, result.listed_price, out_path)
                
        except Exception as e:
            print(f"Error during test: {e}\n")

if __name__ == "__main__":
    run_tests()
