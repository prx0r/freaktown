"""Labelled contact sheets for the newsroom proofs (PIL, no Blender).

    python3 sets/blender/newsroom_sheets.py grid --rows "skin:goodnight,galactic,night-wire" --cols kit \
        --pattern "stills/{row}__default-v1__{col}.png" --out cameras_skins_contact.jpg --title "..."
    python3 sets/blender/newsroom_sheets.py files --out emotions.jpg --cols 4 a.png b.png ...   (label = file stem)

grid: rows x columns of images found by a pattern; a missing image is drawn as a labelled grey cell (never silently
dropped). The camera x skin sheet puts the SAME camera across skins side by side (one column per skin).
"""
import argparse, pathlib

from PIL import Image, ImageDraw, ImageFont

KIT = ["CAM_CRANE_A", "CAM_WIDE", "CAM_MEDIUM", "CAM_CLOSE", "CAM_XCU", "CAM_DESK34", "CAM_WALL", "CAM_SCREEN",
       "CAM_PUSH_A", "CAM_PUSH_B", "CAM_DOLLY_A", "CAM_DOLLY_B"]
FONT = pathlib.Path(__file__).resolve().parent / "newsroom_fonts" / "Inter.ttf"


def _font(s):
    try:
        return ImageFont.truetype(str(FONT), s)
    except Exception:
        return ImageFont.load_default()


def sheet(cells, ncols, cw=480, out="sheet.jpg", title="", col_heads=None, row_heads=None):
    """cells: list of (path or None, label) in row-major order."""
    ch = cw * 9 // 16
    lab = 24
    head = 44 if title else 0
    colh = 28 if col_heads else 0
    rowh = 150 if row_heads else 0
    nrows = (len(cells) + ncols - 1) // ncols
    W = rowh + ncols * (cw + 6) + 6
    H = head + colh + nrows * (ch + lab + 6) + 6
    im = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(im)
    if title:
        d.text((10, 10), title, font=_font(22), fill=(240, 240, 240))
    for c, t in enumerate(col_heads or []):
        d.text((rowh + 6 + c * (cw + 6), head + 4), t, font=_font(17), fill=(255, 210, 120))
    for i, (p, label) in enumerate(cells):
        r, c = divmod(i, ncols)
        x, y = rowh + 6 + c * (cw + 6), head + colh + 6 + r * (ch + lab + 6)
        if row_heads and c == 0:
            d.text((8, y + ch // 2 - 10), row_heads[r], font=_font(16), fill=(255, 210, 120))
        if p and pathlib.Path(p).exists():
            im.paste(Image.open(p).convert("RGB").resize((cw, ch)), (x, y))
        else:
            d.rectangle([x, y, x + cw, y + ch], fill=(60, 60, 66))
            d.text((x + 10, y + ch // 2), "missing", font=_font(16), fill=(200, 120, 120))
        d.text((x + 2, y + ch + 3), label, font=_font(15), fill=(220, 220, 220))
    im.save(out, quality=90)
    return out


def face_stats(png, face_px):
    """Exposure of the anchor's face in a still: mean sRGB of a patch between the eyes and the mouth, the share of
    clipped pixels (any channel >= 0.985) and the warmth R-B (skin reads as skin when it stays clearly > 0; the
    washed-out relit anchor of loop 2 measured ~0.0 at 0.93 mean, i.e. shirt-white)."""
    import numpy as np
    if not face_px:
        return None
    x = np.asarray(Image.open(png).convert("RGB")).astype(np.float32) / 255.0
    H, W = x.shape[:2]
    u, v, r = face_px
    cx, cy, rr = int(u * W), int(v * H), max(3, int(r * H))
    patch = x[max(0, cy - rr):cy + rr, max(0, cx - rr):cx + rr].reshape(-1, 3)
    if not len(patch):
        return None
    m = patch.mean(0)
    return {"mean": [round(float(c), 3) for c in m], "luma": round(float(m @ [0.2126, 0.7152, 0.0722]), 3),
            "clipped": round(float((patch.max(1) >= 0.985).mean()), 3), "warmth": round(float(m[0] - m[2]), 3)}


def facestats(jsons):
    import json
    rows = []
    for j in jsons:
        d = json.loads(pathlib.Path(j).read_text())
        for r in d.get("views", []) + d.get("stills", []):
            png = pathlib.Path(j).parent / r["file"]
            if png.exists():
                rows.append({"file": r["file"], **(face_stats(png, r.get("face_px")) or {})})
    return rows


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grid")
    g.add_argument("--rows", required=True, help="kit | name:a,b,c")
    g.add_argument("--cols", required=True, help="kit | name:a,b,c")
    g.add_argument("--pattern", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--title", default="")
    g.add_argument("--width", type=int, default=420)
    f = sub.add_parser("files")
    f.add_argument("--out", required=True)
    f.add_argument("--cols", type=int, default=4)
    f.add_argument("--title", default="")
    f.add_argument("--width", type=int, default=420)
    f.add_argument("files", nargs="+")
    fs = sub.add_parser("facestats", help="face exposure numbers from views/emotions JSON written next to the stills")
    fs.add_argument("jsons", nargs="+")
    a = ap.parse_args()
    if a.cmd == "facestats":
        import json
        for r in facestats(a.jsons):
            print(json.dumps(r))
        return
    if a.cmd == "grid":
        parse = lambda s: KIT if s == "kit" else s.split(":", 1)[1].split(",")
        rows, cols = parse(a.rows), parse(a.cols)
        cells = [(a.pattern.format(row=r, col=c), f"{r} / {c}") for r in rows for c in cols]
        sheet(cells, len(cols), a.width, a.out, a.title, cols, rows)
    else:
        sheet([(p, pathlib.Path(p).stem.split("__")[-1]) for p in a.files], a.cols, a.width, a.out, a.title)
    print(a.out)


if __name__ == "__main__":
    main()
