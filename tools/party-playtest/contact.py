#!/usr/bin/env python3
"""Per-game contact sheets from shots/<game>/*.png and one combined sheet."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
SHOTS = HERE / "shots"
OUT = HERE / "contact"
OUT.mkdir(exist_ok=True)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except Exception:
        return ImageFont.load_default()


def thumb(p: Path, h: int) -> Image.Image:
    im = Image.open(p).convert("RGB")
    if im.width > im.height:  # stage: crop the top chrome + empty bottom
        im = im.crop((0, 0, im.width, min(im.height, int(im.width * 0.62))))
    w = int(im.width * h / im.height)
    return im.resize((w, h))


def sheet(game: str, files: list, h=300, per_row=6) -> Image.Image:
    cells = []
    for f in files:
        t = thumb(f, h)
        lab = f.stem.split("-", 1)[1][:44]
        cell = Image.new("RGB", (t.width, h + 22), (16, 16, 22))
        cell.paste(t, (0, 22))
        ImageDraw.Draw(cell).text((4, 3), lab, fill=(255, 140, 200), font=font(13))
        cells.append(cell)
    rows = [cells[i:i + per_row] for i in range(0, len(cells), per_row)]
    W = max(sum(c.width for c in r) + 6 * (len(r) + 1) for r in rows)
    H = 50 + sum(h + 22 + 6 for _ in rows)
    out = Image.new("RGB", (W, H), (8, 8, 12))
    d = ImageDraw.Draw(out)
    d.text((10, 10), game, fill=(255, 255, 255), font=font(26))
    y = 50
    for r in rows:
        x = 6
        for c in r:
            out.paste(c, (x, y))
            x += c.width + 6
        y += h + 28
    return out


def main():
    combined = []
    for gdir in sorted(p for p in SHOTS.iterdir() if p.is_dir()):
        files = sorted(gdir.glob("*.png"))
        if not files:
            continue
        files = [f for f in files if "home-game-modes" not in f.name] or files
        im = sheet(gdir.name, files)
        im.save(OUT / f"{gdir.name}_contact.jpg", quality=82)
        # combined: up to 8 key shots per game, smaller
        key = [f for f in files if any(k in f.name for k in
               ("lobby", "collecting", "voting", "drawing", "passfail", "verdict",
                "author", "revealed", "game-over", "left", "reload", "audience",
                "hostless", "play_mobile", "human-acted", "wide_desktop"))]
        seen, pick = set(), []
        for f in key:
            tag = f.stem.split("-", 1)[1]
            if tag not in seen:
                seen.add(tag)
                pick.append(f)
        combined.append(sheet(gdir.name, pick[:9], h=170, per_row=9))
    W = max(i.width for i in combined)
    H = sum(i.height for i in combined) + 60
    out = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(out).text((10, 14), "Freak Town party games — every game played through the real UI",
                             fill=(255, 47, 168), font=font(30))
    y = 60
    for i in combined:
        out.paste(i, (0, y))
        y += i.height
    if out.width > 3000:
        out = out.resize((3000, int(out.height * 3000 / out.width)))
    out.save(HERE / "games_contact.jpg", quality=80)
    print("sheets:", len(combined), "combined:", out.size)


main()
