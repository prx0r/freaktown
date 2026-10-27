import os
#!/usr/bin/env python3
"""Real-browser playthrough (headless Chromium, real mouse/touch input).
usage: pwplay.py freaktionary|quip [BASE]
Hosts on /play, joins phones on /join/<code>, plays to the winner screen,
presses PLAY AGAIN. Screens -> shots/<game>/NN-<who>-<what>.png"""
import json, sys, time, math, re
from pathlib import Path
from playwright.sync_api import sync_playwright

GAME = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8090"
OUT = Path(__file__).parent / "shots" / GAME
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()
N = [0]
LOG = []
def log(*a):
    s = " ".join(str(x) for x in a); LOG.append(s); print(s, flush=True)
def shot(page, who, what):
    N[0] += 1
    page.screenshot(path=str(OUT / f"{N[0]:02d}-{who}-{what}.png"))
INK = "(()=>{const c=document.querySelector(SEL); if(!c) return -1; const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data; let n=0; for(let i=3;i<d.length;i+=4) if(d[i]>0) n++; return n;})()"
def ink(page, sel):
    return page.evaluate(INK.replace("SEL", json.dumps(sel)))
def snap(page, code):
    return page.evaluate(f"fetch('/party/{code}/stream?last_seq=0&once=1').then(r=>r.json()).then(d=>d.snapshot)")
def body(page):
    return page.inner_text("body")
FAIL = []
def check(name, ok, extra=""):
    log(("PASS " if ok else "FAIL ") + name + (f"  [{extra}]" if extra else ""))
    if not ok: FAIL.append(name)

def draw_mouse(page, sel, shape):
    box = page.locator(sel).bounding_box()
    pts = [(box["x"] + box["width"] * x, box["y"] + box["height"] * y) for x, y in shape]
    page.mouse.move(*pts[0]); page.mouse.down()
    for p in pts[1:]:
        page.mouse.move(*p, steps=8)
    page.mouse.up()

def draw_touch(page, sel, shape):
    box = page.locator(sel).bounding_box()
    cdp = page.context.new_cdp_session(page)
    pts = [(box["x"] + box["width"] * x, box["y"] + box["height"] * y) for x, y in shape]
    def ev(t, p):
        cdp.send("Input.dispatchTouchEvent", {"type": t, "touchPoints": ([{"x": p[0], "y": p[1]}] if t != "touchEnd" else [])})
    ev("touchStart", pts[0])
    for a, b in zip(pts, pts[1:]):
        for k in range(1, 9):
            ev("touchMove", (a[0] + (b[0]-a[0])*k/8, a[1] + (b[1]-a[1])*k/8)); time.sleep(0.01)
    ev("touchEnd", pts[-1])

def _proxy(u):
    from urllib.parse import urlparse
    q = urlparse(u)
    d = {"server": f"{q.scheme}://{q.hostname}:{q.port}"}
    if q.username: d["username"] = q.username
    if q.password: d["password"] = q.password
    return d

CIRCLE = [(0.5 + 0.25*math.cos(t/20*2*math.pi), 0.5 + 0.3*math.sin(t/20*2*math.pi)) for t in range(21)]
ZIG = [(0.15, 0.3), (0.35, 0.7), (0.55, 0.3), (0.75, 0.7), (0.9, 0.3)]

with sync_playwright() as pw:
    import os
    if BASE.startswith("https://") and os.environ.get("HTTPS_PROXY"):
        br = pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None, args=["--no-sandbox"],
                                proxy=_proxy(os.environ["HTTPS_PROXY"]))
    else:
        br = pw.chromium.launch(executable_path=os.environ.get("CHROME_PATH") or None, args=["--no-proxy-server", "--no-sandbox"])
    stage = br.new_context(viewport={"width": 1280, "height": 900}).new_page()
    stage.goto(BASE + "/play")
    title = "FREAKTIONARY" if GAME == "freaktionary" else "FUNNIER ENDING"
    card = stage.locator("div", has_text=title).filter(has=stage.locator("button")).last
    card.locator("button").click()
    stage.wait_for_url(re.compile(r"/party/\w+/stage"))
    code = re.search(r"/party/(\w+)/stage", stage.url).group(1)
    log("room", code, stage.url)
    names = ["Ana", "Ben"] if GAME == "freaktionary" else ["Ana", "Ben", "Cy"]
    phones = []
    for nm in names:
        ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        ph = ctx.new_page(); ph.goto(f"{BASE}/join/{code}")
        ph.fill("#n", nm); ph.fill("#f", "Freak " + nm); ph.click("text=JOIN")
        ph.wait_for_url(re.compile(r"/play")); ph.wait_for_selector("text=I'M READY"); ph.click("text=I'M READY")
        phones.append(ph)
    time.sleep(1.5)
    shot(stage, "stage", "lobby")
    if GAME == "quip":
        # deck picker: one click selects, START starts
        stage.click("[data-testid=start-quip-objects]")
        check("deck picker selects on first click", "START POCKET OBJECT" in stage.inner_text("#primary"), stage.inner_text("#primary"))
        stage.click("[data-testid=start-quip-endings]")
        check("deck picker re-selects", "START FUNNIER ENDING" in stage.inner_text("#primary"))
        stage.fill("#rounds", "2")
    stage.click("[data-testid=start]")
    time.sleep(1.5)
    check("START hidden mid-game", not stage.locator("[data-testid=start]").is_visible())
    shot(stage, "stage", "started")

    def by_name(n): return phones[names.index(n)]
    if GAME == "freaktionary":
        for rnd in (1, 2):
            s = snap(stage, code); f = s["freaktionary"]
            check(f"round {rnd} is drawing", f["phase"] == "drawing" and f["round"] == rnd, f"{f['round']} {f['phase']}")
            drawer = by_name(f["drawer"]); guesser = [p for p in phones if p is not drawer][0]
            drawer.wait_for_selector("#draw")
            word = drawer.inner_text("#t").replace("DRAW: ", "").strip()
            log(f"round {rnd}: drawer {f['drawer']} word {word!r}")
            # guesser starts typing BEFORE strokes arrive; polls must not wipe it
            guesser.wait_for_selector("#fld_guess"); guesser.click("#fld_guess"); guesser.keyboard.type("hmm a", delay=40)
            if rnd == 1:
                draw_mouse(drawer, "#draw", CIRCLE); draw_mouse(drawer, "#draw", ZIG)
            else:
                draw_touch(drawer, "#draw", CIRCLE); draw_touch(drawer, "#draw", ZIG)
            time.sleep(2.5)
            s = snap(stage, code); f = s["freaktionary"]
            npts = [len(x["points"]) for x in f["strokes"]]
            check(f"r{rnd} server got 2 continuous strokes", len(npts) == 2 and min(npts) > 20, str(npts))
            check(f"r{rnd} drawing on drawer canvas", ink(drawer, "#draw") > 2000, ink(drawer, "#draw"))
            check(f"r{rnd} drawing on GUESSER phone", ink(guesser, "#watch") > 2000, ink(guesser, "#watch"))
            check(f"r{rnd} drawing on STAGE", ink(stage, "#cv") > 2000, ink(stage, "#cv"))
            val = guesser.input_value("#fld_guess")
            check(f"r{rnd} typed guess survived polls", val == "hmm a", repr(val))
            check(f"r{rnd} focus kept", guesser.evaluate("document.activeElement && document.activeElement.id") == "fld_guess")
            shot(drawer, f["drawer"], f"r{rnd}-drawing"); shot(guesser, "guesser", f"r{rnd}-sees-drawing"); shot(stage, "stage", f"r{rnd}-drawing")
            guesser.fill("#fld_guess", "pigeonz" if word != "pigeonz" else "x"); guesser.click("button.big"); time.sleep(1)
            check(f"r{rnd} wrong guess msg", "Nope" in guesser.inner_text("#sub"), guesser.inner_text("#sub"))
            if rnd == 1:
                guesser.fill("#fld_guess", word); guesser.click("button.big")
            # round 2 left unguessed: host reveals by ADVANCE (no-score round)
            time.sleep(1.5)
            if rnd == 2:
                check("NEXT ROUND hidden mid-round", not stage.locator("[data-testid=advance]").is_visible())
                stage.wait_for_selector("[data-testid=skip]", state="visible", timeout=15000)
                stage.click("[data-testid=skip]"); time.sleep(1.5)
            s = snap(stage, code); f = s["freaktionary"]
            check(f"r{rnd} reveal", f["phase"] == "revealed" and f["word"] == word, f["phase"])
            shot(guesser, "guesser", f"r{rnd}-reveal"); shot(stage, "stage", f"r{rnd}-reveal")
            log("stage text:", stage.inner_text("#big"))
            if rnd == 1:
                stage.wait_for_selector("[data-testid=advance]", state="visible", timeout=8000)
                time.sleep(1.5); stage.click("[data-testid=advance]")  # NEXT ROUND
                stage.evaluate("document.querySelector('[data-testid=advance]').click()")  # fast double click must not skip round 2
                time.sleep(1.5)
                log("hmsg:", stage.inner_text("#hmsg"))
            else:
                time.sleep(1.5); log("final button:", stage.inner_text("[data-testid=advance]"))
                stage.click("[data-testid=advance]"); time.sleep(1.5)
    else:
        for rnd in (1, 2):
            for i, ph in enumerate(phones):
                ph.wait_for_selector("#fld_entry")
                ph.click("#fld_entry"); ph.keyboard.type(f"{names[i]} ending {rnd}", delay=30)
            time.sleep(2.5)
            phones[1].reload(); phones[1].wait_for_selector("#fld_entry"); time.sleep(1)
            check(f"r{rnd} draft survives a page reload", phones[1].input_value("#fld_entry") == f"Ben ending {rnd}", phones[1].input_value("#fld_entry"))
            check(f"r{rnd} typed answers survived polls", all(ph.input_value("#fld_entry") == f"{names[i]} ending {rnd}" for i, ph in enumerate(phones)))
            shot(phones[0], "Ana", f"r{rnd}-typing"); shot(stage, "stage", f"r{rnd}-collecting")
            log("rules on phone:", [t for t in phones[0].inner_text("#body").split("\n") if "votes" in t])
            for ph in phones: ph.click("text=SEND IT"); time.sleep(0.4)
            time.sleep(1.5)
            shot(stage, "stage", f"r{rnd}-voting"); shot(phones[1], "Ben", f"r{rnd}-vote")
            # everyone votes for Ana's line (Ana votes Ben)
            for i, ph in enumerate(phones):
                tgt = "Ben ending" if i == 0 else "Ana ending"
                ph.locator("button.opt", has_text=tgt).click(); time.sleep(0.4)
            time.sleep(1.5)
            s = snap(stage, code); q = s["quip"]
            check(f"r{rnd} scored", q["phase"] == "scored", q["phase"])
            log("stage results:", stage.inner_text("#scores").replace("\n", " | "))
            shot(stage, "stage", f"r{rnd}-results"); shot(phones[2], "Cy", f"r{rnd}-results")
            time.sleep(1.5); stage.click("[data-testid=advance]"); time.sleep(1.5)

    # game over
    time.sleep(1)
    s = snap(stage, code)
    check("game over", s["room_phase"] == "done", s["room_phase"])
    log("result:", json.dumps(s.get("result")))
    log("STAGE banner:", stage.inner_text("#banner"), "|", stage.inner_text("#final").replace("\n", " | "))
    log("PHONE:", phones[0].inner_text("#body").replace("\n", " | "))
    shot(stage, "stage", "winner"); shot(phones[0], names[0], "winner"); shot(phones[1], names[1], "winner")
    # the footer must be stable: same DOM node across polls
    stage.evaluate("window.__again = document.querySelector('[data-testid=again]')")
    time.sleep(2.5)
    check("PLAY AGAIN button stable across polls", stage.evaluate("window.__again === document.querySelector('[data-testid=again]')"))
    stage.click("[data-testid=again]"); time.sleep(1.5)
    s = snap(stage, code)
    check("PLAY AGAIN restarts", s["room_phase"] == "playing" and all(p["score"] == 0 for p in s["scores"]), s["room_phase"])
    check("PLAY AGAIN keeps the round count", s["rounds"] == 2, s["rounds"])
    shot(stage, "stage", "play-again")
    shot(phones[0], names[0], "play-again")
    br.close()
(Path(__file__).parent / f"{GAME}_pw.log").write_text("\n".join(LOG))
print("FAILS:", FAIL)
