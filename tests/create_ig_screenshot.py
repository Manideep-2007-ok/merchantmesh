import os

from PIL import Image, ImageDraw, ImageFont

os.makedirs("data/test_images", exist_ok=True)
img = Image.new("RGB", (500, 800), color=(255, 255, 255))
draw = ImageDraw.Draw(img)

# Try loading font
try:
    font_large = ImageFont.truetype("arial.ttf", 30)
    font_small = ImageFont.truetype("arial.ttf", 20)
except OSError:
    font_large = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Draw mock IG UI
draw.rectangle([(0,0), (500, 60)], fill=(240,240,240)) # Header
draw.text((20, 20), "merchants_store", fill=(0,0,0), font=font_large)

# Product area (mock image)
draw.rectangle([(0, 60), (500, 560)], fill=(200,200,200))
draw.text((150, 300), "[ Photo of a Blue Saree ]", fill=(100,100,100), font=font_large)

# Caption area
caption = """
✨ NEW ARRIVAL ✨
Gorgeous Blue Silk Saree for festive wear!
Price: ₹2500 only.
Minimum 2200 for our followers. 
Hurry, only 2 left in stock!
Link in bio.
"""
draw.text((20, 580), caption, fill=(0,0,0), font=font_small)

img.save("data/test_images/ig_screenshot.jpg")
print("IG screenshot created.")
