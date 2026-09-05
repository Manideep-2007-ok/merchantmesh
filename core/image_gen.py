"""
MerchantMesh - Product Card Image Generator
Generates high-contrast, social-media ready product cards with dynamic overlays and pricing.
"""

import os

from PIL import Image, ImageDraw, ImageFont, ImageOps


def _get_font(size: int) -> ImageFont.ImageFont:
    """Attempts to load a clean TTF font, falling back to scalable default."""
    candidates = [
        "/usr/share/fonts/TTF/JetBrainsMonoNerdFontPropo-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "arial.ttf"
    ]
    for font_path in candidates:
        if os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def create_product_card(
    image_path: str | None,
    product_name: str,
    price: int | None,
    output_path: str
) -> str | None:
    """
    Creates a styled product card by smartly center-cropping and fitting the product photo 
    to 600x600 while preserving aspect ratio, compositing a gradient dark overlay at the base, 
    and rendering product name, price, and branding.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        target_size = (600, 600)
        if image_path and os.path.exists(image_path):
            base_img = Image.open(image_path).convert("RGBA")
            base_img = ImageOps.fit(base_img, target_size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        else:
            base_img = Image.new("RGBA", target_size, (30, 30, 35, 255))
            
        # Create dark gradient overlay at bottom
        overlay = Image.new("RGBA", target_size, (0, 0, 0, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        overlay_height = 140
        top_y = target_size[1] - overlay_height
        
        # Subtle gradient steps for smooth readability
        for i in range(overlay_height):
            alpha = int((i / overlay_height) * 210)
            draw_overlay.line(
                [(0, top_y + i), (target_size[0], top_y + i)],
                fill=(10, 10, 15, alpha)
            )
            
        composed = Image.alpha_composite(base_img, overlay)
        draw = ImageDraw.Draw(composed)
        
        font_large = _get_font(28)
        font_medium = _get_font(20)
        font_small = _get_font(14)
        
        # Product Title (truncated gracefully if too long)
        display_name = product_name.strip()
        if len(display_name) > 30:
            display_name = display_name[:27] + "..."
            
        draw.text((25, target_size[1] - 110), display_name, font=font_large, fill=(255, 255, 255, 255))
        
        # Price Display
        price_text = f"₹{price:,}" if price else "DM for Price"
        draw.text((25, target_size[1] - 55), price_text, font=font_large, fill=(74, 222, 128, 255))
        
        # MerchantMesh Watermark / Badge
        draw.text((target_size[0] - 160, target_size[1] - 45), "MerchantMesh", font=font_small, fill=(200, 200, 200, 180))
        
        # Export as clean RGB JPG
        final_img = composed.convert("RGB")
        final_img.save(output_path, "JPEG", quality=92)
        return output_path
    except Exception as e:
        print(f"❌ Error generating product card: {e}")
        return None



