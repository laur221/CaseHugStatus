from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

assets = Path(__file__).resolve().parents[1] / "casehugauto" / "assets"
assets.mkdir(parents=True, exist_ok=True)

size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

for y in range(size):
    t = y / (size - 1)
    r = int(10 + 20 * t)
    g = int(26 + 80 * (1 - t))
    b = int(56 + 120 * t)
    draw.line([(0, y), (size, y)], fill=(r, g, b, 255))

margin = 60
frame_rect = (margin, margin, size - margin, size - margin)
draw.rounded_rectangle(frame_rect, radius=190, outline=(70, 165, 255, 180), width=18)

stripe = Image.new("RGBA", (size, size), (0, 0, 0, 0))
sd = ImageDraw.Draw(stripe)
sd.rounded_rectangle((190, 430, 834, 590), radius=80, fill=(0, 220, 255, 70))
stripe = stripe.filter(ImageFilter.GaussianBlur(24))
img.alpha_composite(stripe)

draw.ellipse((260, 260, 764, 764), fill=(8, 26, 52, 210), outline=(98, 210, 255, 200), width=12)

text = "CHA"
font = None
for font_name in [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]:
    p = Path(font_name)
    if p.exists():
        font = ImageFont.truetype(str(p), 250)
        break
if font is None:
    font = ImageFont.load_default()

bbox = draw.textbbox((0, 0), text, font=font)
tw = bbox[2] - bbox[0]
th = bbox[3] - bbox[1]
tx = (size - tw) // 2
ty = (size - th) // 2 - 20

draw.text((tx + 5, ty + 7), text, font=font, fill=(0, 0, 0, 130))
draw.text((tx, ty), text, font=font, fill=(151, 232, 255, 255))

draw.rounded_rectangle((340, 700, 684, 726), radius=12, fill=(0, 220, 255, 220))

logo_png = assets / "casehugauto_logo.png"
icon_ico = assets / "casehugauto_icon.ico"
img.save(logo_png, "PNG")

icon = img.resize((256, 256), Image.Resampling.LANCZOS)
icon.save(icon_ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])

print(logo_png)
print(icon_ico)
