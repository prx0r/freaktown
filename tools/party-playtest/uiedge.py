#!/usr/bin/env python3
"""UI edge cases in a real browser: leave mid-round, the room carries on,
REJOIN with the same phone, reload the page (seat token from localStorage),
and keep playing; bad seat shows audience; stage-only room auto-advances."""
import json
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8090"
OUT = Path(__file__).parent / "shots" / "edge-cases"
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
checks = []


def snap(code):
    with urllib.request.urlopen(f"{BASE}/party/{code}/stream?last_seq=0&once=1") as r:
        return json.loads(r.read())["snapshot"]


def check(name, ok):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name, flush=True)


n = [0]


def shoot(page, tag):
    n[0] += 1
    page.screenshot(path=str(OUT / f"{n[0]:02d}-{tag}.png"))


with sync_playwright() as pw:
    br = pw.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-proxy-server", "--no-sandbox"])
    stage = br.new_context(viewport={"width": 1100, "height": 860}).new_page()
    errors = []
    stage.on("pageerror", lambda e: errors.append(str(e)))
    stage.goto(BASE + "/play")
    stage.click("button[data-mode='quip-endings']")
    stage.wait_for_url("**/stage?mode=*")
    code = stage.url.split("/party/")[1].split("/")[0]
    phones = []
    for i in range(3):
        ctx = br.new_context(viewport={"width": 390, "height": 760}, is_mobile=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("dialog", lambda d: d.accept())
        pg.goto(f"{BASE}/join/{code}")
        pg.fill("#n", f"Edge{i + 1}")
        pg.click("text=JOIN")
        pg.wait_for_url("**/play*")
        phones.append(pg)
    # 2-player minimum is enforced from the stage too: start with 1 bot-free seat? (3 here)
    stage.fill("#rounds", "2")
    stage.click("[data-testid='start-quip-endings'] >> nth=0")
    time.sleep(1.5)
    for pg in phones[:2]:
        pg.fill("textarea", f"entry from {pg.url[-6:]}")
        pg.click("button.big")
    time.sleep(1.2)
    shoot(phones[0], "phone1-sent-waiting")
    check("waiting screen after submit", "Waiting for the others" in phones[0].inner_text("#body"))
    phones[2].click("[data-testid=leave]")
    time.sleep(1.5)
    s = snap(code)
    check("leave mid-round: room moves to voting without the leaver", s["quip"]["phase"] == "voting")
    shoot(phones[2], "phone3-left")
    check("leaver sees REJOIN", phones[2].locator("text=REJOIN").count() == 1)
    shoot(stage, "stage-voting-after-leave")
    for pg in phones[:2]:
        pg.locator("button.opt").first.click()
    time.sleep(1.2)
    check("round scores with 2 voters", snap(code)["quip"]["phase"] == "scored")
    phones[2].click("text=REJOIN")
    time.sleep(1.0)
    check("rejoin restores the seat", not [p for p in snap(code)["scores"] if p["left"]])
    stage.click("[data-testid=advance]")
    time.sleep(1.0)
    # reload phone 3: seat token comes back from localStorage, counter restarts
    phones[2].goto(f"{BASE}/party/{code}/play")
    phones[2].wait_for_selector("textarea")
    shoot(phones[2], "phone3-after-reload")
    for pg in phones:
        pg.fill("textarea", "round two " + pg.url[-4:])
        pg.click("button.big")
        time.sleep(0.3)
    time.sleep(1.2)
    s = snap(code)
    check("reloaded phone's input counted (no dup swallow)", s["quip"]["phase"] == "voting")
    # bad seat token -> audience controller, not a crash
    aud = br.new_context(viewport={"width": 390, "height": 760}).new_page()
    aud.goto(f"{BASE}/party/{code}/play?seat=garbage")
    time.sleep(1.5)
    shoot(aud, "bad-seat-audience")
    check("bad seat token gets audience screen", "AUDIENCE" in aud.inner_text("#t"))
    # host disconnect: close the stage; phones finish the round, a fresh
    # read-only stage tab (no host token) sees the room auto-advance
    stage.context.close()
    for pg in phones:
        if pg.locator("button.opt").count():
            pg.locator("button.opt").first.click()
    time.sleep(1.0)
    watcher = br.new_context(viewport={"width": 1100, "height": 860}).new_page()
    watcher.goto(f"{BASE}/party/{code}/stage")
    t0 = time.time()
    while time.time() - t0 < 30 and snap(code)["room_phase"] != "done":
        time.sleep(1)
    time.sleep(1.5)
    shoot(watcher, "hostless-stage-game-over")
    check("host gone: scored screen auto-advances to game over", snap(code)["room_phase"] == "done")
    check("no JS errors", not errors)
    br.close()

(OUT / "result.json").write_text(json.dumps({"checks": checks, "errors": errors}, indent=1))
raise SystemExit(0 if all(ok for _, ok in checks) else 1)
