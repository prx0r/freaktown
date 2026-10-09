#!/usr/bin/env python3
"""Finished Buster samples for the 6 remaining OddHobbStudio listings."""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = "/home/ubuntu/etsysignal/output/samples-buster"
FB = Image.open("/home/ubuntu/etsysignal/roastpet_checkpoint1_demo/02_customer_uploads/buster-001/raw/pet_01_front_face.png").convert("RGB")
HERO = Image.open("/home/ubuntu/etsysignal/output/buster-3cb709/final/hero_2000.png").convert("RGB")
BRICK = Image.open("/tmp/brickshots/brick_threequarter.png").convert("RGB")
BRICK2 = Image.open("/tmp/brickshots/brick_front.png").convert("RGB")


def font(sz):
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", sz)


def circle(im, sz):
    im = im.resize((sz, sz))
    m = Image.new("L", (sz, sz), 0)
    ImageDraw.Draw(m).ellipse((0, 0, sz, sz), fill=255)
    o = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    o.paste(im, (0, 0), m)
    return o


def bg(w, h, t, b):
    im = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3)))
    return im


def head(d, t, p):
    d.text((60, 50), t, font=font(64), fill=(245, 238, 218))
    d.text((60, 130), p, font=font(44), fill=(201, 168, 106))


im = bg(2000, 2000, (18, 20, 40), (50, 30, 60))
d = ImageDraw.Draw(im)
head(d, "BUSTER — Brick Keychain", "Personalised mini · $9.99")
im.paste(BRICK.resize((900, 900)), (200, 420))
ring = Image.new("RGBA", (1150, 1150), (0, 0, 0, 0))
ImageDraw.Draw(ring).ellipse((120, 30, 1030, 940), outline=(200, 200, 210), width=24)
base = im.convert("RGBA")
base.alpha_composite(ring, (80, 300))
im = base.convert("RGB")
d = ImageDraw.Draw(im)
d.text((640, 1620), "Pocket legend, with ring.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/10_brick_keychain.jpg", quality=90)

im = bg(2000, 2000, (35, 20, 45), (60, 35, 60))
d = ImageDraw.Draw(im)
head(d, "BUSTER — Croc Charm", "Shoe jewellery · $7.99")
face = circle(HERO, 800)
im.paste(face, (600, 420), face)
d.ellipse((580, 400, 1420, 1240), outline=(201, 168, 106), width=12)
d.rectangle((960, 1240, 1040, 1420), fill=(180, 180, 190))
d.text((700, 1560), "Snaps into your Crocs.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/11_croc_charm.jpg", quality=90)

im = bg(2000, 2000, (20, 12, 26), (45, 25, 55))
d = ImageDraw.Draw(im)
head(d, "BUSTER & PAL — Couple Figurine", "From your photo · $64.99")
im.paste(BRICK.resize((800, 800)), (180, 480))
im.paste(BRICK2.resize((800, 800)), (1020, 480))
d.text((700, 1450), "Two legends, one shelf.", font=font(44), fill=(245, 238, 218))
badge = circle(FB, 300)
im.paste(badge, (1500, 300), badge)
im.save(f"{OUT}/12_couple_figurine.jpg", quality=90)

im = bg(2000, 2000, (25, 30, 45), (55, 40, 70))
d = ImageDraw.Draw(im)
head(d, "BUSTER — Board Game Pieces", "Meeples, dice, tokens · $16.99")
for x in (200, 750, 1300):
    d.rectangle((x, 500, x + 400, 900), fill=(240, 235, 225), outline=(201, 168, 106), width=8)
face = circle(FB, 220)
im.paste(face, (290, 590), face)
d.text((810, 640), "5", font=font(200), fill=(40, 35, 50))
d.text((1360, 640), "*", font=font(200), fill=(40, 35, 50))
d.text((600, 1150), "Roll with the legend.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/13_board_games.jpg", quality=90)

im = bg(2000, 1400, (30, 25, 20), (60, 50, 35))
d = ImageDraw.Draw(im)
head(d, "BUSTER — Cribbage Pegs", "Magnetic set · $14.99")
for i, x in enumerate([500, 900, 1300]):
    d.rectangle((x, 450, x + 120, 1100), fill=[(200, 60, 60), (240, 235, 225), (60, 90, 200)][i])
    f = circle(FB, 150)
    im.paste(f, (x - 15, 300), f)
d.text((650, 1180), "Peg out in style.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/14_cribbage_pegs.jpg", quality=90)

im = bg(2000, 2000, (15, 15, 25), (40, 30, 50))
d = ImageDraw.Draw(im)
head(d, "BUSTER — Memory Album", "Your stories, pressed · $34.99")
cov = HERO.resize((1100, 1100))
im.paste(cov, (450, 380))
d.rectangle((450, 380, 1550, 1480), outline=(201, 168, 106), width=10)
d.text((700, 1560), "Every legend deserves liner notes.", font=font(44), fill=(245, 238, 218))
im.save(f"{OUT}/15_memory_album.jpg", quality=90)

print("done")
