"""Script to generate high-quality icons and brand assets for Home Assistant and HACS."""
import os
from PIL import Image, ImageDraw, ImageFilter


def create_gradient_squircle(size, radius, color_start, color_end):
    """Create a supersampled rounded rectangle with vertical gradient."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Gradient background
    base = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    for y in range(size):
        ratio = y / float(size)
        r = int(color_start[0] + (color_end[0] - color_start[0]) * ratio)
        g = int(color_start[1] + (color_end[1] - color_start[1]) * ratio)
        b = int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

    # Rounded squircle mask
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = int(size * 0.04)
    mask_draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=255,
    )

    base.paste(img, (0, 0), mask)
    return base


def render_icon(target_size=512):
    # 4x supersampling for clean antialiasing
    scale = 4
    S = target_size * scale

    c_orange_start = (255, 60, 0)   # Tuya vibrant flame orange
    c_orange_end = (255, 140, 0)    # Warm radiant amber
    white = (255, 255, 255, 255)
    glow_yellow = (255, 235, 180, 100)

    # 1. Base gradient tile with rounded corners
    squircle_radius = int(S * 0.22)
    img = create_gradient_squircle(S, squircle_radius, c_orange_start, c_orange_end)

    # Overlay for bulb elements
    overlay = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    cx = S // 2
    bulb_top = int(S * 0.22)
    bulb_r = int(S * 0.20)
    bulb_cy = bulb_top + bulb_r

    # Glow behind bulb
    glow_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.ellipse(
        [cx - bulb_r * 1.5, bulb_cy - bulb_r * 1.4, cx + bulb_r * 1.5, bulb_cy + bulb_r * 1.4],
        fill=glow_yellow,
    )
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(int(scale * 15)))
    img = Image.alpha_composite(img, glow_layer)

    # 2. Bulb Dome (Circle)
    draw.ellipse([cx - bulb_r, bulb_cy - bulb_r, cx + bulb_r, bulb_cy + bulb_r], fill=white)

    # 3. Bulb Tapered Neck
    neck_top_y = bulb_cy + int(bulb_r * 0.45)
    neck_bot_y = bulb_cy + int(bulb_r * 1.35)
    neck_top_w = int(bulb_r * 0.85)
    neck_bot_w = int(bulb_r * 0.52)

    neck_polygon = [
        (cx - neck_top_w, neck_top_y),
        (cx + neck_top_w, neck_top_y),
        (cx + neck_bot_w, neck_bot_y),
        (cx - neck_bot_w, neck_bot_y),
    ]
    draw.polygon(neck_polygon, fill=white)

    # Smooth transition circle inside neck
    draw.ellipse(
        [cx - neck_top_w, neck_top_y - int(bulb_r * 0.3), cx + neck_top_w, neck_top_y + int(bulb_r * 0.3)],
        fill=white,
    )

    # 4. Screw Base
    base_top_y = neck_bot_y
    base_w = neck_bot_w
    ring_h = int(S * 0.024)
    gap = int(S * 0.008)

    base_color = (240, 240, 240, 255)
    for i in range(3):
        ry = base_top_y + i * (ring_h + gap)
        rw = base_w - int(i * base_w * 0.1)
        draw.rounded_rectangle(
            [cx - rw, ry, cx + rw, ry + ring_h],
            radius=int(ring_h * 0.4),
            fill=base_color,
        )

    # Bottom contact
    contact_y = base_top_y + 3 * (ring_h + gap) + int(gap)
    contact_w = int(base_w * 0.45)
    contact_h = int(ring_h * 0.9)
    draw.ellipse([cx - contact_w, contact_y, cx + contact_w, contact_y + contact_h], fill=(200, 200, 200, 255))

    # 5. Filament: Local Wi-Fi waves
    filament_layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fil_draw = ImageDraw.Draw(filament_layer)

    fil_center_y = bulb_cy + int(bulb_r * 0.05)
    fil_color = (255, 100, 0, 240)
    stroke_w = int(S * 0.022)

    dot_r = int(S * 0.032)
    fil_draw.ellipse(
        [cx - dot_r, fil_center_y + int(bulb_r * 0.4) - dot_r, cx + dot_r, fil_center_y + int(bulb_r * 0.4) + dot_r],
        fill=fil_color,
    )

    r1 = int(bulb_r * 0.52)
    arc_y = fil_center_y + int(bulb_r * 0.4)
    fil_draw.arc([cx - r1, arc_y - r1, cx + r1, arc_y + r1], start=215, end=325, fill=fil_color, width=stroke_w)

    r2 = int(bulb_r * 0.82)
    fil_draw.arc([cx - r2, arc_y - r2, cx + r2, arc_y + r2], start=220, end=320, fill=fil_color, width=stroke_w)

    overlay = Image.alpha_composite(overlay, filament_layer)
    img = Image.alpha_composite(img, overlay)

    return img.resize((target_size, target_size), Image.Resampling.LANCZOS)


if __name__ == "__main__":
    os.makedirs("custom_components/tuya_lamp_local/brand", exist_ok=True)

    icon_256 = render_icon(256)
    icon_512 = render_icon(512)

    # 1. Official Home Assistant Brand Directory structure (custom_components/<domain>/brand/)
    icon_256.save("custom_components/tuya_lamp_local/brand/icon.png", "PNG")
    icon_512.save("custom_components/tuya_lamp_local/brand/icon@2x.png", "PNG")
    icon_512.save("custom_components/tuya_lamp_local/brand/logo.png", "PNG")
    icon_512.save("custom_components/tuya_lamp_local/brand/logo@2x.png", "PNG")

    # 2. Direct component root
    icon_512.save("custom_components/tuya_lamp_local/icon.png", "PNG")
    icon_512.save("custom_components/tuya_lamp_local/logo.png", "PNG")

    # 3. Repository root for HACS
    icon_512.save("icon.png", "PNG")
    icon_512.save("logo.png", "PNG")

    print("[+] All icons and brand assets generated successfully:")
    print("    - custom_components/tuya_lamp_local/brand/icon.png (256x256)")
    print("    - custom_components/tuya_lamp_local/brand/icon@2x.png (512x512)")
    print("    - custom_components/tuya_lamp_local/brand/logo.png (512x512)")
    print("    - custom_components/tuya_lamp_local/brand/logo@2x.png (512x512)")
    print("    - custom_components/tuya_lamp_local/icon.png")
    print("    - custom_components/tuya_lamp_local/logo.png")
    print("    - icon.png (root)")
    print("    - logo.png (root)")
