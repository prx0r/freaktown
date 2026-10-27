from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
F = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
def font(n):
    try: return ImageFont.truetype(F, n)
    except Exception: return ImageFont.load_default()
def sheet(game, picks, title, out, h=520):
    cells = []
    for fn, lab in picks:
        im = Image.open(Path("shots") / game / fn).convert("RGB")
        if im.width > im.height: im = im.crop((0, 0, im.width, int(im.width * 0.75)))
        else: im = im.crop((0, 0, im.width, int(im.width * 1.45)))
        t = im.resize((int(im.width * h / im.height), h))
        c = Image.new("RGB", (t.width, h + 30), (16, 16, 22)); c.paste(t, (0, 30))
        ImageDraw.Draw(c).text((6, 6), lab, fill=(255, 150, 200), font=font(16)); cells.append(c)
    per = 4; rows = [cells[i:i+per] for i in range(0, len(cells), per)]
    W = max(sum(c.width for c in r) + 8*(len(r)+1) for r in rows); H = 50 + len(rows)*(h+38)
    S = Image.new("RGB", (W, H), (8, 8, 12)); d = ImageDraw.Draw(S)
    d.text((10, 12), title, fill=(255, 255, 255), font=font(22)); y = 50
    for r in rows:
        x = 8
        for c in r: S.paste(c, (x, y)); x += c.width + 8
        y += h + 38
    S.save(out, quality=85); print(out, S.size)
sheet("freaktionary", [
 ("03-Ana-r1-drawing.png", "R1 drawer phone (mouse drag)"),
 ("04-guesser-r1-sees-drawing.png", "R1 GUESSER phone sees drawing"),
 ("05-stage-r1-drawing.png", "R1 stage shows drawing"),
 ("06-guesser-r1-reveal.png", "R1 reveal on phone"),
 ("08-Ben-r2-drawing.png", "R2 new drawer (touch input)"),
 ("09-guesser-r2-sees-drawing.png", "R2 GUESSER phone sees drawing"),
 ("12-stage-r2-reveal.png", "R2 skipped: nobody got it"),
 ("13-stage-winner.png", "Stage winner + PLAY AGAIN"),
 ("14-Ana-winner.png", "Phone final scores"),
 ("16-stage-play-again.png", "PLAY AGAIN: round 1, 0-0"),
], "FREAKTIONARY — real Chromium playthrough over the public tunnel (real mouse + touch input)", "freaktionary_play.jpg")
sheet("quip", [
 ("03-Ana-r1-typing.png", "Phone: prompt + scoring rule"),
 ("04-stage-r1-collecting.png", "Stage: collecting"),
 ("06-Ben-r1-vote.png", "Phone: vote"),
 ("07-stage-r1-results.png", "Stage: round results"),
 ("08-Cy-r1-results.png", "Phone: round results"),
 ("15-stage-winner.png", "Stage winner + PLAY AGAIN"),
 ("16-Ana-winner.png", "Phone winner screen"),
 ("18-stage-play-again.png", "PLAY AGAIN: scores 0, 2 rounds"),
], "QUIP CLASH (FUNNIER ENDING) — real Chromium playthrough over the public tunnel", "quipclash_play.jpg")
