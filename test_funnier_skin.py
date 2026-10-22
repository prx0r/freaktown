"""Funnier skin + public-bill privacy. Run: python3 test_funnier_skin.py"""
import json
import re
import shutil
import tempfile
import wave
from pathlib import Path

import funnier_skin
import app as appmod
from app import app

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL", name)


def ids_classes(html):
    body = re.sub(r"<style[\s\S]*?</style>", "", html)
    ids = set(re.findall(r"\bid=[\"']?([\w-]+)", body))
    classes = set(c for cl in re.findall(r"\bclass=[\"']([^\"']+)", body) for c in cl.split())
    return ids, classes


tmp = Path(tempfile.mkdtemp())
orig_dir = funnier_skin.FREAK_DIR
orig_app_dir = appmod.FREAK_DIR
funnier_skin.FREAK_DIR = tmp
appmod.FREAK_DIR = tmp


def bundle(slug, name, **extra):
    d = tmp / slug
    d.mkdir()
    (d / "meta.json").write_text(json.dumps({"character": {"name": name}, "duration_s": 42.0,
                                             "created_at": "2026-10-1%d" % len(list(tmp.iterdir())), **extra}))
    with wave.open(str(d / "set.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\0\0" * 800)


try:
    bundle("priscilla-aaaaaa", "Priscilla", listed=True)
    bundle("thomas-bbbbbb", "Thomas", public=True)
    bundle("cathy-prior-cccccc", "Cathy Prior")                 # no flag: hidden
    bundle("lara-prior-dddddd", "Lara Prior", listed=False)     # explicit off
    bundle("e2e-bot-eeeeee", "E2E Bot", listed=True)            # test act: hidden even when listed
    bundle("face-ffffff", "Face Test", listed=True)

    check("listed flag", funnier_skin.is_listed("priscilla-aaaaaa"))
    check("public flag", funnier_skin.is_listed("thomas-bbbbbb"))
    check("default hidden", not funnier_skin.is_listed("cathy-prior-cccccc"))
    check("explicit off", not funnier_skin.is_listed("lara-prior-dddddd"))
    check("test slug", not funnier_skin.is_listed("e2e-bot-eeeeee"))
    check("test name", not funnier_skin.is_listed("face-ffffff"))
    check("unknown", not funnier_skin.is_listed("nope-000000"))

    # the box's bill markup (single + double + unquoted hrefs)
    box = ("<html><head></head><body><p>Headliner: <a href=\"/perform/cathy-prior-cccccc\">Cathy Prior</a></p><div>"
           "<a href='/perform/priscilla-aaaaaa' style='x'><img src='/i.png'><div>Priscilla</div></a>"
           "<a href='/perform/cathy-prior-cccccc' style='x'><img src='/i.png'><div>Cathy Prior</div></a>"
           "<a href=/perform/e2e-bot-eeeeee>next act →</a></div><p>2 acts · live</p></body></html>")
    out = funnier_skin.filter_bill(box)
    check("bill keeps listed", "priscilla-aaaaaa" in out)
    check("bill drops family", "cathy" not in out.lower())
    check("bill drops test (unquoted)", "e2e" not in out)
    check("bill count", "1 acts" in out)
    check("empty headliner removed", "Headliner" not in out)

    c = app.test_client()
    r = c.get("/perform")
    h = r.get_data(as_text=True)
    check("/perform 200", r.status_code == 200)
    check("/perform lists priscilla+thomas", "priscilla-aaaaaa" in h and "thomas-bbbbbb" in h)
    check("/perform hides the rest", not re.search(r"cathy|lara|e2e|face-ffffff", h, re.I))
    check("/perform skinned", "theme.css" in h and "fn-wordmark" in h and "ft-bill" in h and "#ff2fa8" not in h)
    check("/perform header links home", "https://www.funnier.si/" in h)
    for slug in ("cathy-prior-cccccc", "lara-prior-dddddd", "e2e-bot-eeeeee", "face-ffffff", "nope-000000"):
        check(f"/perform/{slug} 404", c.get(f"/perform/{slug}").status_code == 404)
    r = c.get("/perform/priscilla-aaaaaa")
    check("/perform/<listed> reaches the watch page", r.status_code == 200 or "No such set" in r.get_data(as_text=True))

    # /play: mode cards become rails; every data-mode and the mk() script survive
    from party import MODES
    r = c.get("/play")
    h = r.get_data(as_text=True)
    check("/play rails", h.count("class='fn-rail'") >= 1 and h.count("ft-mode fn-card") == len(MODES))
    check("/play every mode", all(f"data-mode='{m}'" in h for m in MODES))
    check("/play script intact", "fetch('/party/create',{method:'POST'})" in h)
    check("/play no pink/mono", "#ff2fa8" not in h and "font-family:monospace" not in h)

    # stage / controller / join / lab: ids and classes the JS uses are all still there
    import party
    raw = {"stage": party.STAGE_TEMPLATE, "controller": party.CONTROLLER_TEMPLATE, "join": party.JOIN_TEMPLATE}
    code = c.post("/party/create").get_json()["code"]
    urls = {"stage": f"/party/{code}/stage", "controller": f"/party/{code}/play", "join": f"/join/{code}"}
    for k, url in urls.items():
        h = c.get(url).get_data(as_text=True)
        i0, c0 = ids_classes(raw[k].replace("__CODE__", code))
        i1, c1 = ids_classes(h)
        check(f"{k} ids kept", i0 <= i1)
        check(f"{k} classes kept", c0 <= c1)
        check(f"{k} skinned", "theme.css" in h and "#ff2fa8" not in h)
    h = c.get("/party/lab").get_data(as_text=True)
    check("lab skinned", "theme.css" in h and "fn-top" in h)

    # non-HTML is untouched: JSON, QR png, SSE stream
    r = c.get(f"/party/{code}/view")
    check("json untouched", r.is_json)
    r = c.get(f"/party/{code}/qr.png")
    check("png untouched", r.mimetype == "image/png")
    r = c.get(f"/party/{code}/stream", buffered=False)
    check("sse untouched", r.mimetype == "text/event-stream" and r.is_streamed)
    r.close()
finally:
    funnier_skin.FREAK_DIR = orig_dir
    appmod.FREAK_DIR = orig_app_dir
    shutil.rmtree(tmp, ignore_errors=True)

print(f"{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
