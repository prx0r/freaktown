"""Funnier skin for Freak Town's public pages (/perform*, /play, /party*, /join*).

Why a response layer instead of editing every template: the box (party.funnier.si) runs commits that are not on
GitHub (stone-face, poker, the /perform bill and live-room APIs). Rewriting the HTML on the way out reskins those
pages too and merges cleanly whatever the box has in app.py / party.py: the only hook is `init(app)` at the bottom
of app.py. Element ids, classes and scripts are left exactly as the views wrote them; only colours, fonts and a
few wrapper classes change, plus the Funnier header.

What it does to an HTML response on a skinned path:
  1. palette: Freak Town pink/cyan/monospace -> Funnier red/gold/Inter Tight (inline styles, <style> blocks and
     colour strings inside scripts alike, so canvas/JS-built UI follows);
  2. links https://www.funnier.si/theme.css (shared tokens + components) and a small local sheet (SKIN_CSS);
  3. puts the Funnier header (wordmark -> www.funnier.si, Freak Town nav, round account icon) at the top of <body>;
  4. /play: groups the mode cards into Funnier rails (party games, Quip Clash decks);
     /perform: turns the bill into a poster grid.

Privacy (the /perform bill is public): an act is on the bill only when its freaks/<slug>/meta.json has
`"listed": true` (or `"public": true`), and test acts (E2E Bot, Share Test, Face Test, ...) never are.
Unlisted acts are stripped from every /perform page and /perform/<slug> returns 404.
    python3 funnier_skin.py status            # every bundle: listed? test?
    python3 funnier_skin.py list SLUG...      # put acts on the bill
    python3 funnier_skin.py unlist SLUG...    # take them off
Kill switch: FUNNIER_SKIN=0 disables the reskin (the privacy filter always stays on).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

FREAK_DIR = Path(__file__).parent / "freaks"
THEME_URL = os.getenv("FUNNIER_THEME_URL", "https://www.funnier.si/theme.css")
HOME_URL = "https://www.funnier.si/"

SKIN_PATHS = re.compile(r"^/(perform(/|$)|play/?$|party(/|$)|join/)")
ACT_PATH = re.compile(r"^/perform/([^/?#]+)")
TEST_ACT = re.compile(r"(^|[-\s_])(e2e|test|testing|smoke|qa)([-\s_]|$)", re.I)

# Freak Town colour -> Funnier token. Matched as whole hex literals only.
PALETTE = {
    "#ff2fa8": "#e8102e", "#ffb7dc": "#ffd6dc", "#2a0a1e": "#2a0a10", "#7a2f5c": "#7a1020",
    "#00d4ff": "#f5c76b", "#8f8": "#5fd38d",
    "#0a0a0f": "#07070a", "#0c0c12": "#0e0e13", "#111116": "#131319", "#14141c": "#131319",
    "#1a1a2e": "#1a1a22", "#111": "#131319", "#282833": "#23232d", "#333": "#23232d",
    "#eee": "#f3f1ec", "#888": "#8d8b93", "#777": "#8d8b93", "#666": "#6f6d75", "#555": "#5d5b63",
}
_HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F])")
_FONT = re.compile(r"font-family:\s*monospace", re.I)

USER_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="9" r="4.2" fill="currentColor"/>'
            '<path d="M3.8 21c.9-4.4 4.2-6.6 8.2-6.6s7.3 2.2 8.2 6.6" fill="currentColor"/></svg>')

SKIN_CSS = """
:root{--ft-font:var(--fn-sans,'Inter Tight',system-ui,sans-serif)}
html body{font-family:var(--ft-font)!important;background-color:var(--fn-bg,#07070a)!important;color:var(--fn-text,#f3f1ec)}
body{background-image:radial-gradient(1200px 500px at 50% -10%,rgba(232,16,46,.16),transparent 60%),radial-gradient(900px 400px at 50% 110%,rgba(245,199,107,.06),transparent 60%)!important;background-attachment:fixed!important}
body.ft-skin{padding-top:0!important}
body.ft-skin>:not(.fn-top):not(script):not(style):not([id=entrance]):not([id=crowdbar]):first-of-type{margin-top:0}
.ft-skin h1,.ft-skin h2:not(.fn-shelf){font-family:var(--fn-display,'Anton',Impact,sans-serif)!important;font-weight:400!important;letter-spacing:.01em!important;line-height:1}
.ft-skin h1{font-size:clamp(36px,6vw,64px)!important;margin:10px 0 8px!important}
.ft-skin #popcard h1{font-size:28px!important}
.ft-skin button,.ft-skin input,.ft-skin textarea,.ft-skin select{font-family:var(--ft-font)!important}
.ft-skin button{font-weight:600;transition:transform .15s,box-shadow .2s,border-color .2s,background .2s}
.ft-skin button:active{transform:scale(.97)}
.ft-skin button:hover{border-color:rgba(232,16,46,.7)!important}
.ft-skin input:not([type=range]):not([type=checkbox]):not([type=radio]),.ft-skin textarea,.ft-skin select{background:var(--fn-panel,#131319)!important;border:1px solid var(--fn-line,#23232d)!important;color:var(--fn-text,#f3f1ec)!important;border-radius:8px!important}
.ft-skin input:focus,.ft-skin textarea:focus,.ft-skin select:focus{outline:none!important;border-color:var(--fn-red,#e8102e)!important;box-shadow:0 0 0 3px rgba(232,16,46,.18)!important}
.ft-skin input[type=range]{accent-color:var(--fn-red,#e8102e)}
.ft-skin canvas{border-color:var(--fn-line,#23232d)!important;border-radius:14px!important}
.ft-skin a{color:var(--fn-text,#f3f1ec)}
/* header */
.ft-skin .fn-top.ft-top{text-align:left;margin:0 0 6px}
.ft-skin .fn-top.ft-top .fn-nav a{font-size:14px}
.ft-skin .fn-top.ft-top .fn-nav a.on{color:var(--fn-text)}
.ft-skin .top .logo{display:none}
.ft-skin .top{color:var(--fn-muted,#8d8b93)!important;font-family:var(--fn-mono,monospace)}
/* rails: /play mode cards */
body.ft-index{text-align:left!important;padding:0 0 48px!important}
body.ft-index>:not(.fn-top):not(script):not(style){max-width:1240px;margin-left:auto!important;margin-right:auto!important;padding-left:clamp(16px,4vw,48px);padding-right:clamp(16px,4vw,48px)}
body.ft-index>h1{margin-top:18px!important}
.ft-rails{margin-top:8px}
.ft-rails .fn-shelf{font-family:var(--fn-sans);font-size:20px;font-weight:700;margin:34px 0 14px}
.ft-rails .fn-shelf{display:flex;align-items:baseline;gap:10px}
.ft-rails .fn-shelf span{font-family:var(--fn-mono,monospace);font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--fn-muted,#8d8b93);font-weight:400}
.ft-rails .fn-rail{grid-auto-columns:minmax(240px,280px)}
.ft-mode.fn-card{margin:0!important;max-width:none!important;border:1px solid var(--fn-line,#23232d)!important;border-radius:14px!important;padding:0!important;overflow:hidden;display:flex;flex-direction:column;background:var(--fn-panel,#131319)}
.ft-mode .ft-poster{aspect-ratio:16/9;display:flex;align-items:flex-end;padding:14px 16px;background:linear-gradient(160deg,#2a0a10,#0b0b0e 72%);border-bottom:1px solid var(--fn-line,#23232d)}
.ft-mode .ft-poster b{font-family:var(--fn-display,'Anton',Impact,sans-serif);font-weight:400;font-size:30px;line-height:.95;letter-spacing:.01em;color:#fff}
.ft-mode.quip .ft-poster{background:linear-gradient(160deg,#2b1d06,#0b0b0e 72%)}
.ft-mode>div:not(.ft-poster){padding:12px 16px 0;font-size:14px!important}
.ft-mode p{margin:auto 0 0!important;padding:12px 16px 16px}
.ft-mode button{width:100%;background:var(--fn-red,#e8102e)!important;color:#fff!important;border:0!important;border-radius:8px!important;font-weight:700!important;font-size:14px!important;padding:10px 14px!important;box-shadow:0 12px 40px -14px var(--fn-red,#e8102e)}
.ft-mode button:hover{background:var(--fn-red2,#ff3d55)!important}
/* /perform bill: poster grid */
.ft-bill{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:18px;margin-top:22px!important;text-align:left}
.ft-bill>a{display:flex!important;flex-direction:column;width:auto!important;margin:0!important;padding:0!important;overflow:hidden;border-radius:12px!important;border:1px solid var(--fn-line,#23232d)!important;background:var(--fn-panel,#131319);transition:transform .25s,border-color .25s,box-shadow .25s}
.ft-bill>a:hover{transform:translateY(-3px);border-color:rgba(232,16,46,.55)!important;box-shadow:0 24px 60px -24px rgba(232,16,46,.35)}
.ft-bill>a img{border-radius:0!important;aspect-ratio:1/1;object-fit:cover;background:linear-gradient(160deg,#2a0a10,#0b0b0e 70%)}
.ft-bill>a>div{padding:0 12px;margin:0!important}
.ft-bill>a>div:nth-of-type(1){font-size:15px!important;font-weight:700;padding-top:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ft-bill>a>div:nth-of-type(2){font-family:var(--fn-mono,monospace);font-size:12px!important;padding-bottom:12px}
.ft-bill>a:first-child{border-color:rgba(245,199,107,.5)!important}
.ft-bill>a:first-child::before{content:'HEADLINER';position:absolute;margin:10px;font-family:var(--fn-mono,monospace);font-size:10px;letter-spacing:.12em;padding:3px 7px;border-radius:4px;background:var(--fn-gold,#f5c76b);color:#0b0b0e}
.ft-bill>a{position:relative}
.ft-bill .ft-ph{display:grid;place-items:center;aspect-ratio:1/1;background:linear-gradient(160deg,#2a0a10,#0b0b0e 72%);font-family:var(--fn-display,'Anton',Impact,sans-serif);font-size:96px;line-height:1;color:rgba(243,241,236,.9);text-shadow:0 0 40px rgba(232,16,46,.45)}
.ft-bill>a:nth-child(3n+2) .ft-ph{background:linear-gradient(160deg,#2b1d06,#0b0b0e 72%)}
.ft-bill>a:nth-child(3n) .ft-ph{background:linear-gradient(160deg,#141a2a,#0b0b0e 72%)}
.ft-skin img[src$="/icon-512.png"]{filter:hue-rotate(28deg) saturate(1.15)}
.ft-skin .fn-top.ft-top{gap:10px;margin-left:calc(50% - 50vw)!important;margin-right:calc(50% - 50vw)!important}
.ft-skin a[href^="/party/lab/"]{display:inline-block;margin-top:4px;text-decoration:none;font-family:var(--fn-mono,monospace);font-size:11px;letter-spacing:.08em;text-transform:uppercase;border:1px solid var(--fn-line,#23232d);border-radius:999px;padding:7px 12px;color:var(--fn-text,#f3f1ec)!important;background:rgba(19,19,25,.85)}
.ft-skin a[href^="/party/lab/"]:hover{border-color:var(--fn-red,#e8102e)}
.ft-skin #code{font-family:var(--fn-display,'Anton',Impact,sans-serif)!important;font-size:64px!important;letter-spacing:.12em!important;color:var(--fn-text,#f3f1ec);text-shadow:0 0 40px rgba(232,16,46,.35)}
.ft-skin #host button,.ft-skin #decks button{background:var(--fn-panel2,#1a1a22);color:var(--fn-text,#f3f1ec);border:1px solid var(--fn-line,#23232d);border-radius:8px;padding:9px 14px;margin:3px;font-size:13px;letter-spacing:.02em;cursor:pointer}
.ft-skin #host>button[onclick*="'start'"]{background:var(--fn-red,#e8102e);border-color:var(--fn-red,#e8102e);color:#fff;box-shadow:0 12px 40px -14px var(--fn-red,#e8102e)}
@media (max-width:600px){.ft-skin .fn-top.ft-top{padding:10px 12px}.ft-skin .fn-top.ft-top .fn-nav a{font-size:13px;padding:6px 7px}.ft-skin .fn-top.ft-top .fn-wordmark{font-size:17px;padding:5px 8px 4px}.ft-skin .fn-userbtn{width:32px;height:32px}}
@media (max-width:600px){.ft-bill{grid-template-columns:repeat(2,1fr);gap:12px}.ft-mode .ft-poster b{font-size:26px}}
"""


# ── listing (privacy) ───────────────────────────────────────────────

def _meta(slug: str) -> dict:
    try:
        return json.loads((FREAK_DIR / slug / "meta.json").read_text())
    except Exception:
        return {}


def is_test_act(slug: str, meta: dict | None = None) -> bool:
    meta = _meta(slug) if meta is None else meta
    name = ((meta.get("character") or {}).get("name") or "")
    return bool(TEST_ACT.search(slug) or TEST_ACT.search(name) or meta.get("test"))


def is_listed(slug: str) -> bool:
    """On the public bill only when explicitly marked, and never a test act."""
    slug = re.sub(r"[^a-z0-9_-]", "", (slug or "").lower())[:64]
    if not slug:
        return False
    meta = _meta(slug)
    return bool(meta.get("listed") is True or meta.get("public") is True) and not is_test_act(slug, meta)


_CARD = re.compile(r"<a\b[^>]*href=([\"']?)/(?:perform|f|w)/([^\"'?#/\s>]+)\1[^>]*>[\s\S]*?</a>", re.I)


def filter_bill(html: str) -> str:
    removed = 0

    def drop(m):
        nonlocal removed
        if is_listed(m.group(2)):
            return m.group(0)
        removed += "<img" in m.group(0)  # a bill card (headliner / next-act links carry no image)
        return ""
    html = _CARD.sub(drop, html)
    html = re.sub(r"<p\b[^>]*>\s*Headliner:\s*</p>", "", html)
    if removed:
        html = re.sub(r"(\d+) acts\b", lambda m: f"{max(0, int(m.group(1)) - removed)} acts", html, count=1)
    return html


# ── reskin ──────────────────────────────────────────────────────────

def _palette(html: str) -> str:
    html = _HEX.sub(lambda m: PALETTE.get(m.group(0).lower(), m.group(0)), html)
    return _FONT.sub("font-family:var(--ft-font)", html)  # no quotes: this lands inside style='...' attributes


def _header(path: str) -> str:
    lab = path.startswith("/party/lab")
    on = lambda yes: " class=on" if yes else ""
    return (f"<header class='fn-top ft-top'><a class='fn-wordmark' href='{HOME_URL}' aria-label='Funnier home'>FUNNIER</a>"
            f"<nav class='fn-nav' aria-label='Freak Town'><a href='/perform'{on(path.startswith('/perform'))}>Tonight&#39;s bill</a>"
            f"<a href='/party'{on(not lab and re.match(r'^/(play|party|join)', path) is not None)}>Party games</a><a href='/party/lab'{on(lab)}>Tech lab</a></nav>"
            f"<a class='fn-userbtn' href='{HOME_URL}#you' aria-label='Your Funnier account'>{USER_SVG}</a></header>")


_MODE_CARD = re.compile(
    r"<div style='border:1px solid #23232d;border-radius:12px;padding:16px;margin:10px auto;max-width:520px'>"
    r"<div style='font-size:18px'>(.*?)</div>([\s\S]*?</p></div>)")


def _mode_rails(html: str) -> str:
    cards = list(_MODE_CARD.finditer(html))
    if not cards:
        return html
    games, quips = [], []
    for m in cards:
        quip = "data-mode='quip-" in m.group(0)
        card = (f"<div class='ft-mode fn-card{' quip' if quip else ''}'><div class='ft-poster'><b>{m.group(1)}</b></div>"
                f"{m.group(2)}")
        (quips if quip else games).append(card)
    rails = "<section class='ft-rails'>"
    if games:
        rails += f"<h2 class='fn-shelf'>Party games <span>{len(games)} modes</span></h2><div class='fn-rail'>{''.join(games)}</div>"
    if quips:
        rails += f"<h2 class='fn-shelf'>Quip Clash <span>{len(quips)} decks</span></h2><div class='fn-rail'>{''.join(quips)}</div>"
    rails += "</section>"
    start, end = cards[0].start(), cards[-1].end()
    return html[:start] + rails + html[end:]


def _poster(m):
    """A bill card without a portrait gets a Funnier monogram poster instead of the pink Freak Town icon."""
    card = m.group(0)
    name = re.search(r"</?(?:img|span)[^>]*>\s*<div[^>]*>([^<]*)</div>", card)
    initial = (name.group(1).strip()[:1] if name else "") or "?"
    return re.sub(r"<img\b[^>]*src=[\"']/icon-512\.png[\"'][^>]*>", f"<span class='ft-ph' aria-hidden='true'>{initial}</span>", card, count=1)


def _bill_grid(html: str) -> str:
    html = _CARD.sub(_poster, html)
    return re.sub(r"<div>(?=<a\b[^>]*href=[\"']?/perform/)", "<div class='ft-bill'>", html, count=1)


def reskin(html: str, path: str) -> str:
    html = _palette(html)
    head = (f"<link rel='stylesheet' href='{THEME_URL}'>"
            f"<style id='funnier-skin'>{SKIN_CSS}</style><meta name='theme-color' content='#07070a'>")
    html = re.sub(r"<meta name=\"theme-color\"[^>]*>", "", html)
    html = re.sub(r"</head>", head + "</head>", html, count=1, flags=re.I)
    html = re.sub(r"<title>([^<]*)Freak Town( Party)?", lambda m: f"<title>{m.group(1)}Freak Town{m.group(2) or ''} · Funnier", html, count=1)
    index = path.rstrip("/") in ("/play", "/party", "/perform")
    html = re.sub(r"<body([^>]*)>", lambda m: _body_open(m.group(1), index) + _header(path), html, count=1, flags=re.I)
    if path.rstrip("/") in ("/play", "/party"):
        html = _mode_rails(html)
    if path.rstrip("/") == "/perform":
        html = _bill_grid(html)
    return html


def _body_open(attrs: str, index: bool = False) -> str:
    cls = "ft-skin fn" + (" ft-index" if index else "")
    if re.search(r"class=", attrs):
        return "<body" + re.sub(r"class=([\"'])", lambda m: f"class={m.group(1)}{cls} ", attrs, count=1) + ">"
    return f"<body class='{cls}'{attrs}>"


# ── wiring ──────────────────────────────────────────────────────────

def init(app):
    """Call once, after every route is defined (bottom of app.py)."""
    from flask import request, abort

    @app.before_request
    def _funnier_private_acts():
        m = ACT_PATH.match(request.path)
        if m and not is_listed(m.group(1)):
            abort(404)

    @app.after_request
    def _funnier_skin(resp):
        path = request.path
        if not SKIN_PATHS.match(path) or resp.is_streamed or resp.direct_passthrough or resp.status_code >= 500:
            return resp
        if not (resp.mimetype or "").startswith("text/html") and not _looks_html(resp):
            return resp
        html = resp.get_data(as_text=True)
        if path.startswith("/perform"):
            html = filter_bill(html)
        if os.getenv("FUNNIER_SKIN", "1") != "0" and "<body" in html.lower():
            html = reskin(html, path)
        resp.set_data(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp

    _fallback_perform_routes(app)


def _looks_html(resp) -> bool:
    if resp.mimetype not in ("text/plain", None, ""):
        return False
    try:
        return resp.get_data(as_text=True)[:200].lstrip().lower().startswith("<!doctype html")
    except Exception:
        return False


def _fallback_perform_routes(app):
    """/perform and /perform/<slug> for checkouts that do not have the box's own bill (repo main does not).
    Same markup as the box's bill so the skin and filter run the same way everywhere."""
    rules = {r.rule for r in app.url_map.iter_rules()}
    import html as _h

    if "/perform" not in rules:
        def perform_bill():
            acts = []
            for d in sorted(FREAK_DIR.iterdir()) if FREAK_DIR.exists() else []:
                meta = _meta(d.name)
                if d.is_dir() and meta and (d / "set.wav").exists():
                    acts.append((meta.get("created_at", ""), d.name, meta))
            acts.sort(reverse=True)
            cards = []
            for _, slug, meta in acts:
                name = _h.escape((meta.get("character") or {}).get("name", slug))
                img = f"/freaks/{slug}/portrait.png" if (FREAK_DIR / slug / "portrait.png").exists() else "/icon-512.png"
                dur = meta.get("duration_s", 0)
                cards.append(f"<a href='/perform/{slug}' style='display:inline-block;width:150px;margin:8px;padding:10px;border:1px solid #282833;"
                             f"border-radius:12px;color:#eee;text-decoration:none;vertical-align:top'><img src='{img}' style='width:100%;border-radius:8px'>"
                             f"<div style='font-size:13px;margin-top:6px'>{name}</div><div style='color:#666;font-size:11px'>{dur}s</div></a>")
            head = ""
            if acts:
                s, m = acts[0][1], acts[0][2]
                head = f"<p style=\"color:#888;\">Headliner: <a href=\"/perform/{s}\">{_h.escape((m.get('character') or {}).get('name', s))}</a></p>"
            page = ("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                    "<title>TONIGHT — Freak Town Live</title>\n<style>body{background:#0a0a0f;color:#eee;font-family:monospace;text-align:center;padding:32px 16px}\n"
                    "a{color:#ff2fa8}</style></head><body>\n<div style=\"font-size:12px;letter-spacing:2px;color:#ff2fa8;\">🎪 FREAK TOWN · LIVE</div>\n"
                    f"<h1>TONIGHT'S BILL</h1>\n{head}\n<div>{''.join(cards)}</div>\n"
                    f"<p style=\"color:#555;font-size:12px;margin-top:16px\">{len(cards)} acts · pre-rendered sets,\nlive audience · predicted heat is heuristic v0</p>\n</body></html>")
            return page, 200, {"Content-Type": "text/html; charset=utf-8"}
        app.add_url_rule("/perform", "funnier_perform_bill", perform_bill)
        app.add_url_rule("/perform/", "funnier_perform_bill_slash", perform_bill)

    if "/perform/<slug>" not in rules and "/perform/<path:slug>" not in rules:
        def perform_act(slug):
            render = app.view_functions.get("watch_set")
            if render is None:
                abort_404()
            return render(slug)
        app.add_url_rule("/perform/<slug>", "funnier_perform_act", perform_act)


def abort_404():
    from flask import abort
    abort(404)


# ── CLI ─────────────────────────────────────────────────────────────

def _set_listed(slugs, value: bool):
    for slug in slugs:
        p = FREAK_DIR / slug / "meta.json"
        if not p.exists():
            print(f"skip {slug}: no bundle")
            continue
        meta = json.loads(p.read_text())
        meta["listed"] = value
        p.write_text(json.dumps(meta, indent=2))
        print(f"{'listed' if value else 'unlisted'} {slug}" + ("  (test act: stays off the bill)" if value and is_test_act(slug, meta) else ""))


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else "status"), sys.argv[2:]
    if cmd == "status":
        for d in sorted(FREAK_DIR.iterdir()) if FREAK_DIR.exists() else []:
            if d.is_dir() and (d / "meta.json").exists():
                meta = _meta(d.name)
                print(f"{'LISTED  ' if is_listed(d.name) else 'hidden  '}{'test ' if is_test_act(d.name, meta) else '     '}{d.name}  "
                      f"({(meta.get('character') or {}).get('name', '')})")
    elif cmd in ("list", "unlist") and args:
        _set_listed(args, cmd == "list")
    else:
        print(__doc__)
