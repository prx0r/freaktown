#!/usr/bin/env python3
"""Build finished Etsy sample images for every oddhobb product.

Demo star: Buster (roastpet_checkpoint1_demo photos + prior outputs).
Brick renders: /tmp/brickshots (scripts/render_brick.py).
Output: /home/ubuntu/etsysignal/output/samples-buster/
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = "/home/ubuntu/etsysignal/output/samples-buster"
os.makedirs(OUT, exist_ok=True)
FB = "/home/ubuntu/etsysignal/roastpet_checkpoint1_demo/02_customer_uploads/buster-001/raw/pet_01_front_face.png"
HERO = "/home/ubuntu/etsysignal/output/buster-3cb709/final/hero_2000.png"
CARD = "/home/ubuntu/etsysignal/output/buster-3cb709/final/card_front.png"

FB_IMG = Image.open(FB).convert("RGB")
HERO_IMG = Image.open(HERO).convert("RGB")


def font(sz):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def circle_crop(im, size):
    im = im.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def bg(w, h, top, bot):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return im


def header(d, title, price):
    d.text((60, 50), title, font=font(64), fill=(245, 238, 218))
    d.text((60, 130), price, font=font(44), fill=(201, 168, 106))


# 1. brick hero composite -------------------------------------------------------
brick = Image.open("/tmp/brickshots/brick_front.png").convert("RGB")
W, H = 2000, 2000
im = bg(W, H, (20, 12, 26), (45, 25, 55))
d = ImageDraw.Draw(im)
header(d, "BUSTER — Brick Figure", "Personalised · £20.00")
im.paste(brick.resize((1100, 1100)), (120, 420))
badge = circle_crop(FB_IMG, 420)
im.paste(badge, (1360, 480), badge)
d.text((1360, 940), "Sculpted from", font=font(36), fill=(203, 191, 165))
d.text((1360, 990), "your photos", font=font(36), fill=(203, 191, 165))
d.text((120, 1600), "Same model, one sculpt, many products.", font=font(36), fill=(160, 140, 115))
im.save(f"{OUT}/01_brick_figure.jpg", quality=90)

# turntable sheet ----------------------------------------------------------------
turns = [Image.open(f"/tmp/brickshots/turn_{i:02d}.png").convert("RGB").resize((480, 480))
         for i in range(8)]
sheet = bg(2000, 1100, (20, 12, 26), (45, 25, 55))
d = ImageDraw.Draw(sheet)
header(d, "BUSTER — 360° turntable", "Every angle approved.")
for i, th in enumerate(turns):
    sheet.paste(th, ((i % 4) * 500 + 10, 230 + (i // 4) * 440))
sheet.save(f"{OUT}/02_brick_turntable.jpg", quality=88)

# 2. ornament --------------------------------------------------------------------
im = bg(2000, 2000, (25, 40, 30), (60, 20, 25))
d = ImageDraw.Draw(im)
header(d, "BUSTER — Christmas Ornament", "Personalised · £15.00")
face = circle_crop(HERO_IMG, 1100)
im.paste(face, (450, 330), face)
d.ellipse((430, 310, 1570, 1450), outline=(201, 168, 106), width=14)
d.text((830, 180), "★", font=font(90), fill=(201, 168, 106))
d.text((560, 1560), "Merry Christmas, you legend.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/03_ornament.jpg", quality=90)

# 3. keychain --------------------------------------------------------------------
im = bg(2000, 2000, (18, 20, 40), (50, 30, 60))
d = ImageDraw.Draw(im)
header(d, "BUSTER — Pet Keychain", "Personalised · £15.00")
fob = circle_crop(HERO_IMG, 900).resize((900, 900))
ring = Image.new("RGBA", (1100, 1100), (0, 0, 0, 0))
ImageDraw.Draw(ring).ellipse((100, 20, 1000, 920), outline=(200, 200, 210), width=26)
im.paste(fob, (550, 620), fob)
base = im.convert("RGBA")
base.alpha_composite(ring, (450, 480))
im = base.convert("RGB")
d = ImageDraw.Draw(im)
d.text((640, 1620), "Take the legend everywhere.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/04_keychain.jpg", quality=90)

# 4. mug wrap (production artwork) -------------------------------------------------
wrap = Image.new("RGB", (3000, 1200), (250, 248, 242))
d = ImageDraw.Draw(wrap)
d.text((110, 80), "BUSTER'S MORNING BRIEFING", font=font(72), fill=(30, 25, 40))
face = circle_crop(FB_IMG, 700)
wrap.paste(face, (150, 320), face)
d.text((950, 420), "Coffee first.", font=font(80), fill=(30, 25, 40))
d.text((950, 520), "Judgement second.", font=font(80), fill=(30, 25, 40))
d.text((950, 660), "Same model. One sculpt.", font=font(48), fill=(120, 110, 100))
d.text((110, 1080), "Mug wrap artwork · £19.99 · printed to order", font=font(40), fill=(120, 110, 100))
wrap.save(f"{OUT}/05_mug_wrap.jpg", quality=90)

# 5. cushion ----------------------------------------------------------------------
im = bg(2000, 2000, (40, 25, 35), (70, 45, 55))
d = ImageDraw.Draw(im)
header(d, "BUSTER — Cushion", "Personalised · £29.99")
pil = HERO_IMG.resize((1150, 1150))
ImageDraw.Draw(pil).rounded_rectangle((0, 0, 1150, 1150), radius=90, outline=(201, 168, 106), width=16)
im.paste(pil, (425, 330))
d.text((620, 1560), "A throne for their face.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/06_cushion.jpg", quality=90)

print("samples done:", sorted(os.listdir(OUT)))
