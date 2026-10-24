"""Newsroom graphics package (PIL, no Blender): a skin's branding painted onto the studio's live surfaces.

    python3 sets/blender/newsroom_gfx.py cards --skin goodnight --prog episode/programme.json --out episode/cards
    python3 sets/blender/newsroom_gfx.py cards --skin galactic --sample --out /tmp/cards      # stills: a sample story

Live surfaces (named slots of the master studio):
    wall cards   news_wall_screen (the LED wall): title, story<k> (kicker + headline + credit), ambient (the skin's art
                 with no text: what the wall shows whenever a camera would crop a headline), signoff
    desk band    news_desk_brand: the show name across the desk front
    overlays     composited last over the rendered frames (newsroom_finish.py): the bug, lower thirds, the animated
                 intro title sequence and the outro sign-off card (then film grain)

Card styles (brand.card_style in news_skins/<skin>.json): paper-sun (Goodnight), starfield (Galactic), wire (Night
Wire), and generic: any other value draws a clean layout from the palette over the skin's own background image
(brand.assets.card_background, a path relative to news_skins/), so a new skin needs no code. Fonts are vendored OFL
fonts in sets/blender/newsroom_fonts; a skin may name its own font file in news_skins/ (brand.fonts.*).
"""
import argparse, json, math, pathlib, random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
FONTS = HERE / "newsroom_fonts"
SKINS = HERE / "news_skins"
CARD = (2048, 1024)
BAND = (2048, 224)


def load_skin(name):
    p = pathlib.Path(name)
    if not p.exists():
        p = SKINS / f"{name}.json"
    return json.loads(p.read_text())


def rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def _font_path(fn):
    for d in (SKINS, FONTS):
        if (d / fn).exists():
            return d / fn
    return FONTS / "Inter.ttf"


def font(skin, role, size, weight=None):
    f = ImageFont.truetype(str(_font_path(skin["brand"]["fonts"].get(role, "Inter.ttf"))), max(6, int(size)))
    w = weight or (skin["brand"].get("head_weight") if role == "head" else None)
    try:
        names = [n.decode() if isinstance(n, bytes) else n for n in f.get_variation_names()]
        if w and w in names:
            f.set_variation_by_name(w)
        elif role == "head" and "Bold" in names:
            f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def wrap(draw, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=f) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, skin, role, text, box_w, box_h, start, min_size=24, lh=1.18, max_lines=3):
    s = start
    while s > min_size:
        f = font(skin, role, s)
        ls = wrap(draw, text, f, box_w)
        if len(ls) <= max_lines and len(ls) * s * lh <= box_h:
            return f, ls, s
        s = int(s * 0.92)
    f = font(skin, role, min_size)
    return f, wrap(draw, text, f, box_w)[:max_lines], min_size


def grad(size, top, bot):
    w, h = size
    im = Image.new("RGBA", size)
    d = ImageDraw.Draw(im)
    for y in range(h):
        u = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (bot[i] - top[i]) * u) for i in range(3)) + (255,))
    return im


def paper_noise(im):
    n = Image.effect_noise(im.size, 40).convert("L")
    return Image.blend(im.convert("RGB"), Image.merge("RGB", (n, n, n)), 0.04).convert("RGBA")


def background(skin, size):
    """The skin's own background image (brand.assets.card_background) if it has one, else None."""
    a = skin["brand"].get("assets", {}).get("card_background")
    if a and (SKINS / a).exists():
        return Image.open(SKINS / a).convert("RGBA").resize(size)
    return None


# ---- wall cards -----------------------------------------------------------------------------------------------------
def card(skin, kind, story=None, date="", size=CARD):
    st = skin["brand"].get("card_style", "generic")
    painter = {"paper-sun": card_paper_sun, "starfield": card_starfield, "wire": card_wire}.get(st, card_generic)
    return painter(skin, kind, story or {}, date, size)


def _sun(d, pal, cx, cy, r):
    acc, acc2 = rgb(pal["accent"]), rgb(pal["accent2"])
    for k in range(15):
        a = math.pi + (k + 0.5) * math.pi / 15
        d.line([(cx + math.cos(a) * r * 1.22, cy + math.sin(a) * r * 1.22), (cx + math.cos(a) * r * (1.55 + 0.12 * (k % 2)),
                 cy + math.sin(a) * r * (1.55 + 0.12 * (k % 2)))], fill=acc[:3] + (190,), width=max(3, int(r * 0.03)))
    for i in range(int(r), 0, -2):
        u = i / r
        d.ellipse([cx - i, cy - i, cx + i, cy + i], fill=tuple(int(acc[j] * (1 - u * 0.25) + acc2[j] * u * 0.25) for j in range(3)) + (255,))


def _headline_block(d, skin, kind, story, date, x, y, w, h, start, kfill, hfill, kicker_font=None, lh=1.18):
    kicker = (date if kind == "title" else story.get("source", "")).upper()
    head = skin["brand"]["title"] if kind == "title" else story.get("title", "")
    head = head.upper() if skin["brand"].get("caps") else head
    d.text((x, y), kicker, font=kicker_font or font(skin, "body", 44, "SemiBold"), fill=kfill)
    f, ls, s = fit_text(d, skin, "head", head, w, h, start, lh=lh)
    yy = y + 100
    for ln in ls:
        d.text((x, yy), ln, font=f, fill=hfill)
        yy += s * lh
    return yy


def card_paper_sun(skin, kind, story, date, size):
    pal = skin["brand"]["palette"]
    W, H = size
    im = background(skin, size) or paper_noise(grad(size, rgb(pal["paper"]), rgb(pal["paper2"])))
    sun = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(sun)
    if kind == "signoff":
        cx, cy, r = int(W * 0.78), int(H * 0.36), int(H * 0.17)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb(pal["accent"]))
        d.ellipse([cx - r + int(r * 0.45), cy - r - int(r * 0.15), cx + r + int(r * 0.45), cy + r - int(r * 0.15)], fill=(0, 0, 0, 0))
    else:
        _sun(d, pal, int(W * (0.76 if kind != "ambient" else 0.5)), int(H * 0.98), int(H * (0.27 if kind != "ambient" else 0.36)))
    im = Image.alpha_composite(im, sun.filter(ImageFilter.GaussianBlur(1.2)))
    d = ImageDraw.Draw(im)
    ink, muted, acc2 = rgb(pal["ink"]), rgb(pal["muted"]), rgb(pal["accent2"])
    m = int(W * 0.055)
    d.rectangle([m * 0.5, m * 0.5, W - m * 0.5, H - m * 0.5], outline=rgb(pal["accent"]), width=6)
    if kind in ("title", "story"):
        _headline_block(d, skin, kind, story, date, m * 1.5, m * 1.6, W * 0.62, H * 0.5, 150 if kind == "title" else 120, acc2, ink, lh=1.2)
        d.line([(m * 1.5, m * 1.6 + 66), (m * 1.5 + 120, m * 1.6 + 66)], fill=rgb(pal["accent"]), width=6)
        d.line([(m * 1.5, H - m * 2.3), (W - m * 1.5, H - m * 2.3)], fill=muted[:3] + (120,), width=3)
        foot = skin["brand"]["tagline"] if kind == "title" else (f"via {story.get('source', '')}" if story.get("source") else "")
        d.text((m * 1.5, H - m * 2.0), foot, font=font(skin, "italic", 38), fill=muted)
    elif kind == "ambient":
        d.text((m * 1.5, m * 1.6), skin["brand"]["title"], font=font(skin, "head", 64), fill=muted[:3] + (200,))
        if date:
            d.text((m * 1.5, m * 1.6 + 90), date, font=font(skin, "italic", 38), fill=muted[:3] + (170,))
    elif kind == "signoff":
        d.text((m * 1.5, H * 0.3), skin["brand"].get("signoff", "Goodnight."), font=font(skin, "italic", 170), fill=ink)
        d.text((m * 1.5, H * 0.3 + 230), skin["brand"]["title"], font=font(skin, "body", 46, "SemiBold"), fill=acc2)
    return im


def _stars(size, pal, seed=5, n=1400):
    W, H = size
    im = grad(size, rgb(pal["paper2"]), rgb(pal["paper"]))
    neb = Image.new("RGBA", size, (0, 0, 0, 0))
    g = ImageDraw.Draw(neb)
    r = random.Random(seed)
    for _ in range(9):
        cx, cy, rr = r.random() * W, r.random() * H * 0.8, (0.12 + r.random() * 0.25) * W
        c = rgb(pal["accent2"] if r.random() < 0.6 else pal["accent"])
        g.ellipse([cx - rr, cy - rr * 0.5, cx + rr, cy + rr * 0.5], fill=c[:3] + (34,))
    im = Image.alpha_composite(im, neb.filter(ImageFilter.GaussianBlur(W * 0.04)))
    d = ImageDraw.Draw(im, "RGBA")
    for _ in range(n):
        x, y, b = r.random() * W, r.random() * H, r.random() ** 3
        s = 1 + 3.2 * b
        d.ellipse([x - s, y - s, x + s, y + s], fill=(255, 255, 255, int(90 + 165 * b)))
    return im


def card_starfield(skin, kind, story, date, size):
    pal = skin["brand"]["palette"]
    W, H = size
    im = background(skin, size) or _stars(size, pal)
    d = ImageDraw.Draw(im, "RGBA")
    acc, acc2, ink, muted = rgb(pal["accent"]), rgb(pal["accent2"]), rgb(pal["ink"]), rgb(pal["muted"])
    # a planet limb along the bottom right, an orbit ring
    pl = Image.new("RGBA", size, (0, 0, 0, 0))
    p = ImageDraw.Draw(pl)
    cx, cy, rr = W * (0.82 if kind != "ambient" else 0.5), H * 1.55, H * 0.95
    for i in range(int(rr), int(rr * 0.7), -3):
        u = (rr - i) / (rr * 0.3)
        p.ellipse([cx - i, cy - i, cx + i, cy + i], fill=tuple(int(acc2[j] * (1 - u) * 0.6 + 8) for j in range(3)) + (255,))
    p.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=acc[:3] + (230,), width=8)
    im = Image.alpha_composite(im, pl.filter(ImageFilter.GaussianBlur(2)))
    d = ImageDraw.Draw(im, "RGBA")
    d.arc([W * 0.05, H * 0.55, W * 1.2, H * 1.35], 190, 330, fill=acc[:3] + (110,), width=4)
    m = int(W * 0.06)
    if kind in ("title", "story"):
        d.rectangle([m, m + 8, m + 10, m + 60], fill=acc)
        _headline_block(d, skin, kind, story, date, m + 34, m + 4, W * 0.8, H * 0.5, 170, acc, ink, lh=1.1)
        if kind == "story" and story.get("source"):
            d.text((m + 34, H - m - 50), "TRANSMISSION: " + story["source"].upper(), font=font(skin, "body", 30, "SemiBold"), fill=muted)
    elif kind == "ambient":
        d.text((m, m), skin["brand"]["title"].upper(), font=font(skin, "head", 60), fill=acc[:3] + (200,))
    elif kind == "signoff":
        so = skin["brand"].get("signoff", "Goodnight.")
        d.text((m, H * 0.26), so.upper() if skin["brand"].get("caps") else so, font=font(skin, "head", 180), fill=ink)
        d.text((m, H * 0.26 + 250), skin["brand"]["title"].upper(), font=font(skin, "body", 44, "Bold"), fill=acc)
    return im


def card_wire(skin, kind, story, date, size):
    pal = skin["brand"]["palette"]
    W, H = size
    im = background(skin, size) or grad(size, rgb(pal["paper2"]), rgb(pal["paper"]))
    d = ImageDraw.Draw(im, "RGBA")
    acc, acc2, ink, muted = rgb(pal["accent"]), rgb(pal["accent2"]), rgb(pal["ink"]), rgb(pal["muted"])
    r = random.Random(11)
    for _ in range(900):
        x, y = r.random() * W, r.random() * H
        if math.sin(x / W * 9.0) * math.cos(y / H * 6.0 + 1.3) > 0.15:
            d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=acc[:3] + (60,))
    for k in range(5):
        x0 = -200 + k * 70
        d.polygon([(x0, H), (x0 + 40, H), (x0 + 340, 0), (x0 + 300, 0)], fill=acc2[:3] + (90,))
    m = int(W * 0.07)
    if kind in ("title", "story"):
        d.rectangle([m, m, m + 220, m + 80], fill=acc)
        lab, fl = ("WIRE" if kind == "story" else "LIVE"), font(skin, "head", 60)
        bb = d.textbbox((0, 0), lab, font=fl)
        d.text((m + (220 - (bb[2] - bb[0])) / 2 - bb[0], m + (80 - (bb[3] - bb[1])) / 2 - bb[1]), lab, font=fl, fill=ink)
        kicker = (date if kind == "title" else story.get("source", "")).upper()
        d.text((m + 250, m + 14), kicker, font=font(skin, "body", 44, "SemiBold"), fill=muted)
        head = skin["brand"]["title"] if kind == "title" else story.get("title", "")
        head = head.upper() if skin["brand"].get("caps") else head
        f, ls, s = fit_text(d, skin, "head", head, W * 0.82, H * 0.52, 170, lh=1.08)
        y = m + 130
        for ln in ls:
            d.text((m, y), ln, font=f, fill=ink)
            y += s * 1.08
        d.rectangle([m, H - m - 14, W - m, H - m - 6], fill=acc)
    elif kind == "ambient":
        d.text((m + 300, m), skin["brand"]["title"].upper(), font=font(skin, "head", 72), fill=acc[:3] + (200,))
    elif kind == "signoff":
        so = skin["brand"].get("signoff", "Goodnight.")
        d.text((m, H * 0.26), so.upper(), font=font(skin, "head", 190), fill=ink)
        d.rectangle([m, H * 0.26 + 320, m + 420, H * 0.26 + 332], fill=acc)
    return im


def card_generic(skin, kind, story, date, size):
    """Any skin without a built-in painter: its background image (or a palette gradient) + a clean layout."""
    pal = skin["brand"]["palette"]
    W, H = size
    im = background(skin, size) or grad(size, rgb(pal["paper2"]), rgb(pal["paper"]))
    d = ImageDraw.Draw(im, "RGBA")
    acc, ink, muted = rgb(pal["accent"]), rgb(pal["ink"]), rgb(pal["muted"])
    m = int(W * 0.06)
    if kind in ("title", "story"):
        _headline_block(d, skin, kind, story, date, m, m, W * 0.8, H * 0.5, 160, acc, ink)
        d.rectangle([m, H - m - 10, W * 0.45, H - m - 2], fill=acc)
    elif kind == "ambient":
        d.text((m, m), skin["brand"]["title"], font=font(skin, "head", 60), fill=muted)
    else:
        d.text((m, H * 0.3), skin["brand"].get("signoff", "Goodnight."), font=font(skin, "head", 170), fill=ink)
    return im


def desk_band(skin, size=BAND):
    pal = skin["brand"]["palette"]
    W, H = size
    a = skin["brand"].get("assets", {}).get("desk_background")
    im = Image.open(SKINS / a).convert("RGBA").resize(size) if a and (SKINS / a).exists() else Image.new("RGBA", size, rgb(pal["desk_bg"]))
    d = ImageDraw.Draw(im)
    f, ls, s = fit_text(d, skin, "head", skin["brand"]["desk_text"], W * 0.7, H * 0.62, int(H * 0.6), max_lines=1)
    tw = d.textlength(ls[0], font=f)
    bb = d.textbbox((0, 0), ls[0], font=f)
    d.text(((W - tw) / 2, (H - (bb[3] - bb[1])) / 2 - bb[1]), ls[0], font=f, fill=rgb(pal["desk_ink"]))
    d.line([(W * 0.08, H * 0.16), (W * 0.92, H * 0.16)], fill=rgb(pal["accent"]), width=4)
    d.line([(W * 0.08, H * 0.84), (W * 0.92, H * 0.84)], fill=rgb(pal["accent"]), width=4)
    return im


def write_cards(skin, out, prog=None, sample=False, date=""):
    """Paint every wall card the programme needs (+ desk band). Returns {card name: path}; writes cards.json."""
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    stories = (prog or {}).get("stories") or ([{"title": "Euclid discovers new comet", "source": "ESA"}] if sample else [])
    date = date or (prog or {}).get("date", "") or "22 October 2026"
    paths = {}
    for kind in ("title", "ambient", "signoff"):
        p = out / f"card_{kind}.png"
        card(skin, kind, date=date).convert("RGB").save(p)
        paths[kind] = p.name
    for k, st in enumerate(stories):
        p = out / f"card_story{k}.png"
        card(skin, "story", st, date).convert("RGB").save(p)
        paths[f"story{k}"] = p.name
    desk_band(skin).convert("RGB").save(out / "brand.png")
    paths["brand"] = "brand.png"
    (out / "cards.json").write_text(json.dumps(paths, indent=1))
    return paths


# ---- overlays (composited over the rendered frames) --------------------------------------------------------------------
def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


class Overlay:
    """Per-frame graphics over a W x H frame: bug, lower thirds, intro title sequence, outro card."""

    def __init__(self, skin, prog, W=1280, H=720):
        self.skin, self.prog, self.W, self.H = skin, prog, W, H
        self.k = W / 1280.0
        self.pal = skin["brand"]["palette"]
        self._cache = {}

    def f(self, role, size, weight=None):
        key = (role, size, weight)
        if key not in self._cache:
            self._cache[key] = font(self.skin, role, size * self.k, weight)
        return self._cache[key]

    def frame(self, t):
        """RGBA overlay at programme time t (ms)."""
        p, W, H, k = self.prog, self.W, self.H, self.k
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im, "RGBA")
        intro, outro, dur = p["intro_ms"], p["outro_ms"], p["duration_ms"]
        if t < intro:
            self.intro(d, im, t / intro)
        elif t >= dur - outro:
            self.outro(d, im, (t - (dur - outro)) / outro)
        else:
            a = int(255 * ease((t - intro) / 600.0))
            acc = rgb(self.pal["accent"])
            d.ellipse([22 * k, 22 * k, 34 * k, 34 * k], fill=acc[:3] + (a,))
            d.text((44 * k, 17 * k), self.skin["brand"]["title"].upper(), font=self.f("body", 17, "SemiBold"),
                   fill=(255, 255, 255, int(a * 0.92)))
            for lt in p.get("lowers", []):
                if lt["t_ms"] <= t < lt["t_ms"] + lt["dur_ms"]:
                    self.lower(d, (t - lt["t_ms"]) / 1000.0, lt["dur_ms"] / 1000.0, lt)
        return im

    def lower(self, d, s, dur, lt):
        k, H, pal = self.k, self.H, self.pal
        u = min(ease(s / 0.45), 1.0 - ease((s - (dur - 0.35)) / 0.35))
        if u <= 0:
            return
        title = lt["title"].upper() if self.skin["brand"].get("caps") else lt["title"]
        sub = lt.get("sub", "")
        ft, fs = self.f("head", 30), self.f("body", 18, "Medium")
        tw = max(d.textlength(title, font=ft), d.textlength(sub, font=fs)) + 60 * k
        x0, y0 = 70 * k, H - 150 * k
        w = tw * u
        d.rectangle([x0, y0, x0 + w, y0 + 62 * k], fill=rgb(pal["lower_bg"])[:3] + (int(232 * u),))
        d.rectangle([x0, y0 + 62 * k, x0 + w * 0.85, y0 + 92 * k], fill=rgb(pal["accent"])[:3] + (int(240 * u),))
        d.rectangle([x0 - 8 * k, y0, x0 - 2 * k, y0 + 92 * k], fill=rgb(pal["accent"])[:3] + (int(255 * u),))
        if u > 0.6:
            a = int(255 * ease((u - 0.6) / 0.4))
            d.text((x0 + 26 * k, y0 + 12 * k), title, font=ft, fill=rgb(pal["lower_ink"])[:3] + (a,))
            d.text((x0 + 26 * k, y0 + 66 * k), sub, font=fs, fill=rgb(pal["lower_bg"])[:3] + (a,))

    def intro(self, d, im, u):
        """Title sequence over the crane-in: a curtain in the skin's colour opens, the title rises word by word, a
        rule wipes under it, tagline and date fade in, then it lifts away to reveal the studio."""
        k, W, H, pal, b = self.k, self.W, self.H, self.pal, self.skin["brand"]
        acc = rgb(pal["accent"])
        curtain = 1.0 - ease((u - 0.02) / 0.22)
        if curtain > 0:
            d.rectangle([0, 0, W, H], fill=rgb(pal["lower_bg"])[:3] + (int(255 * curtain),))
        out = 1.0 - ease((u - 0.8) / 0.17)
        if out <= 0:
            return
        title = b["title"].upper() if b.get("caps") else b["title"]
        ft = self.f("head", 86)
        x = (W - d.textlength(title, font=ft)) / 2
        y = H * 0.36
        sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sc).rectangle([0, y - 60 * k, W, y + 190 * k], fill=(0, 0, 0, int(120 * out * min(1.0, u * 4))))
        im.alpha_composite(sc.filter(ImageFilter.GaussianBlur(30 * k)))
        for i, w in enumerate(title.split()):
            wu = ease((u - 0.12 - i * 0.07) / 0.18)
            d.text((x, y + (1 - wu) * 40 * k), w, font=ft, fill=(255, 255, 255, int(255 * wu * out)))
            x += d.textlength(w + " ", font=ft)
        half = 260 * k * ease((u - 0.3) / 0.25)
        d.rectangle([W / 2 - half, y + 112 * k, W / 2 + half, y + 118 * k], fill=acc[:3] + (int(255 * out),))
        tu = ease((u - 0.42) / 0.2)
        ftg = self.f("italic", 26)
        d.text(((W - d.textlength(b["tagline"], font=ftg)) / 2, y + 134 * k), b["tagline"], font=ftg,
               fill=(255, 255, 255, int(220 * tu * out)))
        date = self.prog.get("date", "")
        if date:
            fd = self.f("body", 18, "SemiBold")
            d.text(((W - d.textlength(date.upper(), font=fd)) / 2, y - 40 * k), date.upper(), font=fd, fill=acc[:3] + (int(230 * tu * out),))
        style = b.get("intro_fx", b.get("card_style"))
        if style == "wire":
            d.rectangle([0, H * 0.3, W * ease(u / 0.3), H * 0.3 + 8 * k], fill=acc[:3] + (int(255 * out),))
        elif style == "starfield":
            r = random.Random(3)
            for _ in range(70):         # warp streaks rushing out of the centre
                a, s0 = r.random() * 6.283, r.random()
                rr = (s0 + u * 1.6) % 1.0
                L = 40 * k * rr
                cx, cy = W / 2 + math.cos(a) * rr * W * 0.6, H / 2 + math.sin(a) * rr * H * 0.6
                d.line([(cx, cy), (cx + math.cos(a) * L, cy + math.sin(a) * L)], fill=(220, 240, 255, int(200 * out * (1 - rr))), width=max(1, int(2 * k)))

    def outro(self, d, im, u):
        k, W, H, pal, b = self.k, self.W, self.H, self.pal, self.skin["brand"]
        a = ease((u - 0.1) / 0.3)
        f = self.f("italic" if b.get("card_style") == "paper-sun" else "head", 80)
        so = b.get("signoff", "Goodnight.")
        so = so.upper() if b.get("caps") else so
        sc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sc).rectangle([0, H * 0.33, W, H * 0.68], fill=(0, 0, 0, int(120 * a)))
        im.alpha_composite(sc.filter(ImageFilter.GaussianBlur(30 * k)))
        d.text(((W - d.textlength(so, font=f)) / 2, H * 0.38), so, font=f, fill=(255, 255, 255, int(255 * a)))
        fs = self.f("body", 20, "SemiBold")
        t2 = b["title"].upper()
        d.text(((W - d.textlength(t2, font=fs)) / 2, H * 0.38 + 110 * k), t2, font=fs, fill=rgb(pal["accent"])[:3] + (int(240 * a),))
        cr = "Studio, picture and score made procedurally in Blender. Original music."
        fc = self.f("body", 13)
        d.text(((W - d.textlength(cr, font=fc)) / 2, H * 0.38 + 146 * k), cr, font=fc, fill=(255, 255, 255, int(150 * a)))
        fade = ease((u - 0.82) / 0.18)
        if fade > 0:
            d.rectangle([0, 0, W, H], fill=(0, 0, 0, int(255 * fade)))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("cards")
    c.add_argument("--skin", required=True)
    c.add_argument("--prog", default="")
    c.add_argument("--sample", action="store_true")
    c.add_argument("--date", default="")
    c.add_argument("--out", required=True)
    a = ap.parse_args()
    prog = json.loads(pathlib.Path(a.prog).read_text()) if a.prog else None
    print(json.dumps(write_cards(load_skin(a.skin), a.out, prog, a.sample, a.date)))


if __name__ == "__main__":
    main()
