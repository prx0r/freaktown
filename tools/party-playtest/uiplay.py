#!/usr/bin/env python3
"""Drive the real web UI (stage + phones) with headless Chromium for one
full game, screenshotting every phase.

usage: python3 uiplay.py MODE [n_phones] [rounds]
  MODE: freaktionary | roast-relay | freeze-night | quip-<deck> | pack:<NAME>
Screens land in shots/<MODE>/NN-<who>-<phase>.png
"""
import json
import random
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8090"
MODE = sys.argv[1]
NPH = int(sys.argv[2]) if len(sys.argv) > 2 else 3
ROUNDS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
OUT = Path(__file__).parent / "shots" / MODE.replace(":", "_").replace(" ", "_")
OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.png"):
    f.unlink()
WORDS = ["air fryer", "traffic cone", "divorce court", "pigeon", "Tesco",
         "haunted Roomba", "LinkedIn", "cryptocurrency", "dentist", "karaoke"]
urllib.request.install_opener(urllib.request.build_opener(urllib.request.ProxyHandler({})))
LOG = []


def snap(code):
    with urllib.request.urlopen(f"{BASE}/party/{code}/stream?last_seq=0&once=1", timeout=10) as r:
        d = json.loads(r.read())
    return d["snapshot"], d["events"]


def phase_key(s):
    for k in ("freaktionary", "roast-relay", "quip", "freeze-night"):
        if s.get(k):
            sub = s[k]
            pk = f"p{s['pack']['idx']}:" if s.get("pack") else ""
            return f"{pk}{s['mode']}|{sub.get('round')}|{sub.get('kind') or ''}|{sub.get('phase')}"
    return s["room_phase"]


def main():
    shot_n = [0]

    def shoot(page, who, tag):
        shot_n[0] += 1
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in tag)[:60]
        p = OUT / f"{shot_n[0]:02d}-{who}-{safe}.png"
        page.screenshot(path=str(p))
        return p

    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path="/usr/bin/chromium",
                                args=["--no-proxy-server", "--no-sandbox"])
        stage_ctx = br.new_context(viewport={"width": 1100, "height": 860})
        stage = stage_ctx.new_page()
        errors = []
        stage.on("pageerror", lambda e: errors.append(f"stage: {e}"))
        stage.goto(BASE + "/play")
        shoot(stage, "home", "game-modes")
        pack = MODE[5:] if MODE.startswith("pack:") else None
        mode_btn = "freaktionary" if pack else MODE
        stage.click(f"button[data-mode='{mode_btn}']")
        stage.wait_for_url("**/stage?mode=*")
        code = stage.url.split("/party/")[1].split("/")[0]
        phones = []
        for i in range(NPH):
            ctx = br.new_context(viewport={"width": 390, "height": 760}, is_mobile=True,
                                 has_touch=True)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e, i=i: errors.append(f"phone{i}: {e}"))
            pg.goto(f"{BASE}/join/{code}")
            pg.fill("#n", f"Player{i + 1}")
            pg.fill("#f", ["Martin Lamp", "Doug Deadline", "Pete Pebble", "Madame C"][i % 4])
            if i == 0:
                shoot(pg, "phone1", "join")
            pg.click("text=JOIN")
            pg.wait_for_url("**/play*")
            pg.wait_for_selector("text=I'M READY")
            pg.click("text=I'M READY")
            phones.append({"page": pg, "sent": set(), "rng": random.Random(i), "guessed": set()})
        time.sleep(1.5)
        shoot(phones[0]["page"], "phone1", "lobby")
        shoot(stage, "stage", "lobby")
        if ROUNDS and MODE != "freeze-night":
            stage.fill("#rounds", str(ROUNDS))
        if MODE == "roast-relay":
            stage.fill("#target", "the group chat")
        if pack:
            stage.click(f"text={pack}")
        else:
            stage.click(f"[data-testid='start-{MODE}'] >> nth=0")
        time.sleep(1.2)
        seen = set()
        t0 = time.time()
        last_change = time.time()
        winner = None
        while time.time() - t0 < 100:
            s, _ = snap(code)
            key = phase_key(s)
            if key not in seen:
                seen.add(key)
                last_change = time.time()
                time.sleep(1.4)  # let stage + phones repaint
                shoot(stage, "stage", key)
                shoot(phones[0]["page"], "phone1", key)
                if "drawing" in key or "passfail" in key:
                    for j, ph in enumerate(phones[1:], 2):
                        shoot(ph["page"], f"phone{j}", key)
                LOG.append(key)
            if s["room_phase"] == "done":
                winner = stage.locator("[data-testid=winner]").inner_text(timeout=5000)
                break
            acted = False
            for ph in phones:
                pg = ph["page"]
                if pg.locator("#draw").count():
                    box = pg.locator("#draw").bounding_box()
                    x0, y0 = box["x"] + 40, box["y"] + 40
                    pg.mouse.move(x0, y0)
                    pg.mouse.down()
                    for k in range(1, 12):
                        pg.mouse.move(x0 + k * 25, y0 + (k % 3) * 40, steps=2)
                        time.sleep(0.03)
                    pg.mouse.up()
                    acted = True
                    continue
                ta = pg.locator("textarea")
                if ta.count() and not ta.input_value():
                    if pg.locator("#fld_guess").count():
                        w = ph["rng"].choice([w for w in WORDS if w not in ph["guessed"]] or WORDS)
                        ph["guessed"].add(w)
                        ta.fill(w)
                    else:
                        txt = f"{pg.title()[:0]}line {ph['rng'].randint(10, 99)} from P{phones.index(ph) + 1}"
                        ta.fill(txt)
                        ph["sent"].add(txt)
                    if pg.locator("input[type=checkbox]").count() and ph["rng"].random() < .5:
                        pg.locator("input[type=checkbox]").check()
                    pg.click("button.big")
                    acted = True
                    continue
                opts = pg.locator("button.opt")
                if opts.count():
                    texts = opts.all_inner_texts()
                    idx = [i for i, t in enumerate(texts) if t not in ph["sent"]] or list(range(len(texts)))
                    if pg.locator("button.big").count():  # last-lash multi-pick
                        for i in idx[:2]:
                            opts.nth(i).click()
                        pg.click("button.big")
                    else:
                        opts.nth(ph["rng"].choice(idx)).click()
                    acted = True
            sub = key.split("|")[-1]
            if not acted and sub in ("scored", "revealed"):
                stage.click("[data-testid=advance]")
                time.sleep(0.8)
            elif not acted and time.time() - last_change > 12:
                stage.click("[data-testid=advance]")  # stand-in for the 90 s timer
                last_change = time.time()
            time.sleep(0.5)
        time.sleep(1.5)
        shoot(stage, "stage", "game-over")
        shoot(phones[0]["page"], "phone1", "game-over")
        # play again -> lobby
        again = stage.locator("[data-testid=again]")
        played_again = False
        if again.count():
            again.click()
            time.sleep(1.5)
            s, _ = snap(code)
            played_again = s["room_phase"] == "playing" and all(p["score"] == 0 for p in s["scores"]) \
                and (not pack or (s.get("pack") or {}).get("name") == pack)
            shoot(stage, "stage", "play-again")
        stage.click("[data-testid=lobby]")
        time.sleep(1.8)
        s, _ = snap(code)
        shoot(phones[0]["page"], "phone1", "back-to-lobby")
        res = {"mode": MODE, "code": code, "winner": winner, "phases": LOG,
               "played_again": played_again, "back_to_lobby": s["room_phase"] == "lobby",
               "js_errors": errors, "secs": round(time.time() - t0, 1),
               "shots": len(list(OUT.glob("*.png")))}
        print(json.dumps(res))
        (OUT / "result.json").write_text(json.dumps(res, indent=1))
        br.close()
        raise SystemExit(0 if winner and not errors and res["back_to_lobby"] else 1)


main()
