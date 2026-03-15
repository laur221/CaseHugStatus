from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

assets = Path(__file__).resolve().parents[1] / "casehugauto" / "assets"
assets.mkdir(parents=True, exist_ok=True)

size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

cx, cy = size // 2, size // 2

ring_r = 360
ring_w = 20
segments = 18
for i in range(segments):
    if i % 2 == 0:
        start = (360 / segments) * i - 90
        end = start + (360 / segments) * 0.65
        d.arc((cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r), start, end, fill=(120, 150, 190, 220), width=ring_w)

d.arc((cx-ring_r, cy-ring_r, cx+ring_r, cy+ring_r), -85, -75, fill=(32, 239, 255, 255), width=ring_w+4)

body = (260, 360, 764, 700)
for i in range(120):
    t = i / 119
    col = (
        int(18 + 40*(1-t)),
        int(36 + 55*(1-t)),
        int(62 + 85*(1-t)),
        235,
    )
    y = int(body[1] + (body[3]-body[1]) * t)
    d.rounded_rectangle((body[0], y, body[2], y+4), radius=36, fill=col)

d.rectangle((body[0], 505, body[2], 515), fill=(22, 36, 58, 255))

handle_outer = (405, 296, 619, 390)
handle_inner = (444, 328, 580, 390)
d.rounded_rectangle(handle_outer, radius=34, fill=(124, 150, 178, 210))
d.rounded_rectangle(handle_inner, radius=24, fill=(20, 40, 65, 255))

panel = (370, 540, 654, 670)
d.rounded_rectangle(panel, radius=20, fill=(15, 30, 50, 255), outline=(80, 105, 130, 220), width=6)

bars = [
    (404, 574, 494, 644, (24, 220, 255, 245)),
    (520, 560, 610, 644, (26, 237, 255, 250)),
    (616, 590, 644, 644, (90, 112, 140, 245)),
]
for x1,y1,x2,y2,c in bars:
    d.rounded_rectangle((x1,y1,x2,y2), radius=8, fill=c)

glow = Image.new("RGBA", (size, size), (0,0,0,0))
gd = ImageDraw.Draw(glow)
gd.ellipse((250, 250, 774, 774), outline=(30, 220, 255, 80), width=16)
glow = glow.filter(ImageFilter.GaussianBlur(10))
img = Image.alpha_composite(img, glow)

d.ellipse((320, 690, 704, 760), fill=(0,0,0,70))

logo_path = assets / "casehugauto_logo.png"
img.save(logo_path, "PNG")

sidebar_path = assets / "casehugauto_sidebar.png"
img.resize((256,256), Image.Resampling.LANCZOS).save(sidebar_path, "PNG")

ico_path = assets / "casehugauto_icon.ico"
img.resize((256,256), Image.Resampling.LANCZOS).save(ico_path, format="ICO", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])

print(logo_path)
print(sidebar_path)
print(ico_path)
