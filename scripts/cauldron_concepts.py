#!/usr/bin/env python3
"""Cauldron concept frames via Cloudflare Workers AI ($0, daily neurons).

12 drafts: 4 main stage, 3 comedian POV, 2 bar, 2 wing, 1 booth.
Saves static/concepts/<shot>.png + <shot>.json (prompt, model, seed, time).
Gallery: /cauldron (app.py). Winners become Marble contextFrames anchors.

Creds: CF_API_TOKEN + CF_ACCOUNT_ID from environment (source /root/.r2-env).
Never printed, never logged. No inference spend — free-tier neurons only.

  source /root/.r2-env && /usr/bin/python3 scripts/cauldron_concepts.py
"""
import datetime
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "static" / "concepts"
MODEL = os.environ.get("CF_MODEL", "@cf/black-forest-labs/flux-1-schnell")

BANS = ("empty room, static environment only, no people, no animals, "
        "no audience, no faces, no windows, no daylight, "
        "no candles, no string lights, no text, no logos, "
        "sharp focus, clear depth with foreground midground background, "
        "visible floor walls and ceiling, near-dark 2700K house light with "
        "one hard bright 4000K spotlight haze cone as the key light, "
        "dingy basement comedy club, damp peeling near-black brick, "
        "beer and fog, photorealistic interior photograph, "
        "all frames share identical lighting and color temperature")
SIGIL = "chalk cauldron outline, smudged, on back wall"

NEUTRAL = ("soft neutral diffuse 5000K architectural illumination, moderately bright, readable brick texture, visible corners, no hard shadows, no colored light, no pitch-black areas, wide architectural photograph, natural perspective, physically plausible room geometry, ")

# SHELL rule (2026-10-17): the venue GLB is the bare shell ONLY. No mic
# stand, no furniture, no curtains, no sigil in shell frames — those are
# added layers we own. Dressed frames (mic etc.) are composition previews,
# never Atlas anchors.
BARE = ("bare empty shell: no mic stand, no stools, no tables, no chairs, "
        "no curtains, no wall marks, no signs, no text, empty stage deck, "
        "empty floor, ")

SHOTS = [
    ("main-wide", "wide shot from back of room: small stained wood stage with ONE brass mic stand center and nothing else, black crooked curtains each side, hard spotlight haze cone from booth to the mic, scarred cocktail tables and folding chairs facing stage, " + SIGIL + ", green EXIT sign glowing over back-left door, " + BANS),
    ("main-medium", "medium shot of comedy stage front: stained wood planks with ring marks and tape residue, one worn pale circle center, single brass-weighted mic stand with ball mic and drooping cable, damp brick back wall with peeling paint, " + SIGIL + ", black crooked traveler curtain left edge, spotlight haze, " + BANS),
    ("main-close", "close-up of lone brass microphone on stand center stage: worn brass base, steel pole, ball mic, cable drooping to stained deck, shallow depth, blurred damp brick and faint chalk marks behind, single hard spotlight, dust in haze beam, " + BANS),
    ("sigil-detail", "detail of back wall: large smudged chalk cauldron outline hand-drawn on damp peeling near-black brick over older green paint, spotlight spill grazing across, dark, moody, " + BANS),
    ("pov-center", "comedian's point of view from center stage behind the mic looking out: rows of empty folding chairs and cocktail tables in near-darkness, wood and fabric catching the spotlight spill, green EXIT sign far back-left, bar bottle blur back-right, haze in spotlight beam, " + BANS),
    ("pov-left", "comedian's point of view from stage-left wing: angled view across mic stand to dark empty tables, black crooked curtain foreground right, spotlight cone crossing frame, brick side wall with water stain and peeling handbills, " + BANS),
    ("pov-low", "low comedian's point of view over the microphone: ball mic foreground bottom, looking down past spotlight haze onto dark tables and chairs, sticky concrete floor aisles worn gray, " + BANS),
    ("bar-tables", "audience point of view seated at scarred black cocktail table: across worn tabletop to small distant stage with lone mic stand in spotlight haze cone, folding chairs rows, dark, intimate, " + BANS),
    ("bar-shelf", "from behind the bar: counter edge foreground, blurred bottle shelf amber glow, across the dark room to the lit stage with single mic and chalk sigil wall, concrete floor, " + BANS),
    ("wing-left", "from the stage-left wing behind the crooked black curtain: sliver view through curtain gap of lit mic stand and haze cone, curtain fabric large dark foreground, anticipation, backstage dark, " + BANS),
    ("wing-right", "from stage-right wing beside tall wooden stool: past curtain edge to empty spotlighted stage, chalk sigil wall, house dark beyond, quiet before showtime, " + BANS),
    ("booth", "high rear booth view of whole room: full cellar, tiny lit stage with mic far below in haze cone, grid of dark tables and chairs, bar suggestion back-right, EXIT green dot, near-dark 11:40pm forever, " + BANS),
    # Batch 2 (2026-10-17): main landscape stage view explorations — the
    # canonical viewer frame. Winner becomes the inpainting ref for all else.
    ("main2-a", "front-on wide view of small comedy stage from mid-room: stained wood stage, ONE brass mic stand dead center in a thick visible spotlight haze cone, black crooked curtains framing both sides, smudged chalk cauldron outline centered on damp brick behind, dark tables foreground out of focus, " + BANS),
    ("main2-b", "wide stage view with curtains dominant: tall black crooked traveler curtains half-open and looming both sides, small lit stage between them with lone mic, chalk sigil wall glowing faintly in spill, rows of empty chairs curving in dark, " + BANS),
    ("main2-c", "wide stage view, brick dominant: heavily peeling damp near-black brick walls closing in, small stage with single mic stand, green EXIT sign bright back-left, deep shadows, oppressive cozy cellar, chalk cauldron outline above stage, " + BANS),
    ("main2-d", "seated eye-level view from front-row table: across scarred tabletop edge to full stage, mic stand center in haze, curtain tops cut by frame top, intimate close-to-stage feel, folding chairs either side dark, " + BANS),
    ("main2-e", "slightly wide stage view including bar hint: stage left-of-center with mic in spotlight, black curtains, chalk wall, right edge shows dark bar counter with amber bottle blur, tables and chairs across middle ground, " + BANS),
    ("main2-f", "moody minimal stage view: house nearly black, single brutal spotlight cone onto lone mic, chalk sigil barely visible in spill, curtain edges dissolving to dark, maximum contrast dingy cellar, " + BANS),
    # Batch 3 (2026-10-17): BARE SHELL explorations — no mic, no furniture,
    # no curtains. These are the Atlas anchor candidates. Dressed batches
    # (main/main2) are composition previews only, never anchors.
    ("shell-a", "front-on wide view of small bare comedy stage from mid-room: empty stained wood stage deck with nothing on it, distressed matte-black painted brick back wall bare, empty concrete floor, " + BARE + NEUTRAL),
    ("shell-b", "wide bare room view: shallow permanent raised stage with bare deck, peeling damp near-black brick all around, exposed ceiling pipes and beams, empty concrete floor, bare curtain rails with no fabric, recessed bar alcove with bare counter along one wall, " + BARE + NEUTRAL),
    ("shell-c", "seated eye-level view of bare stage: empty deck edge-on, matte-black brick behind, empty floor foreground, irregular structural column one side, " + BARE + NEUTRAL),
    ("shell-d", "point of view from bare empty stage looking out over empty floor: rear wall with narrow entrance recess, bar alcove along one wall, low industrial ceiling with ducts, " + BARE + NEUTRAL),
    ("shell-e", "high rear view of bare room: full empty cellar, small bare stage far wall below, empty floor, bar alcove one side, entrance recess rear, ceiling pipes, " + BARE + NEUTRAL),
    ("shell-f", "side angle of bare stage and room: empty deck, dark charcoal brick side wall with water stain and mortar texture, empty floor, bare curtain rail, crooked brick arch around the stage, " + BARE + NEUTRAL),
    # Batch 4 (2026-10-17): fresh mains, SURROUND layout — tables gathered
    # AROUND the small stage (Cellar formula), not cinema rows. Dressed
    # composition previews; winner becomes the inpainting ref.
    ("main3-a", "front-on wide view of small comedy stage with scarred cocktail tables and chairs gathered AROUND it on three sides, ONE brass mic stand center in spotlight haze cone, black crooked curtains, smudged chalk cauldron outline on damp brick, green EXIT sign, intimate surround, " + BANS),
    ("main3-b", "wide stage view from a side table: tables hemming in the small lit stage, mic stand in haze, curtain looming near camera, brick walls close and dark, cozy pressure, " + BANS),
    ("main3-c", "rear view over the crowd tables to the stage: table tops and chair backs foreground framing the lit mic, chalk sigil wall, EXIT green far left, room feels full even empty, " + BANS),
    ("main3-d", "low wide view: small stage slightly above table level, mic in cone, surround tables tight, low ceiling felt, warm dark reds and ambers in the wood, " + BANS),
    ("main3-e", "corner angle: stage diagonal, tables wrapping two sides, bar hint with amber blur at frame edge, curtain fold foreground, " + BANS),
    ("main3-f", "straight-on symmetrical: centered mic, symmetric curtains, tables mirrored both sides, chalk sigil centered above, poster-perfect lineup-night framing, " + BANS),
    # Batch 5 (2026-10-17): SHORT prompts, Comedy Cellar mental model. Small
    # intimate NYC basement: low ceiling, brick, tables crowded around a tiny
    # stage. Bans enforced by validator, not the prompt.
    ("main4-a", "tiny underground comedy club in a New York basement, small wooden stage with a single microphone stand, round tables and chairs crowded close around the stage, dark brick walls, low ceiling with pipes, dim warm light, intimate, photorealistic, empty, no people"),
    ("main4-b", "side view of a cramped brick comedy cellar, small lit stage with one mic, tables hemming it in on two sides, black curtain edge, warm dim bulbs, exposed duct overhead, photorealistic, empty, no people"),
    ("main4-c", "view from the back of a packed-feeling tiny comedy club toward the stage, table tops and chair backs in foreground, lone microphone in a cone of warm light, brick behind, low ceiling, photorealistic, empty, no people"),
    ("main4-d", "low warm wide shot of a basement comedy room, distressed black brick, worn wooden stage, cocktail tables surrounding it, soft amber glow and deep shadows, cozy and grungy, photorealistic, empty, no people"),
    ("main4-e", "corner of an underground comedy club with a small bar shelf and bottles at the edge, tables facing a brick-walled stage with one mic, dim and smoky, intimate, photorealistic, empty, no people"),
    ("main4-f", "straight symmetrical shot of a tiny comedy stage, centered mic stand, dark curtains both sides, brick arch feel, tables mirrored left and right, single warm spotlight, downtown basement vibe, photorealistic, empty, no people"),
]


def gen(prompt, token, acct):
    # NOTE: CF schnell accepts prompt ONLY (width/height/steps/seed rejected
    # 400/5006). Output is model-default square; Atlas cover-resize +
    # center-crops anchors onto 1280x720, so square is fine. Dims are read
    # back from the PNG header into the sidecar.
    body = json.dumps({"prompt": prompt}).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{MODEL}",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    ctype = r.headers.get("Content-Type", "")
    if "json" in ctype:
        # CF schnell returns {"result":{"image":"<base64 jpeg>"}} as JSON.
        payload = json.loads(data.decode())
        b64 = (payload.get("result") or {}).get("image", "")
        if not b64:
            raise RuntimeError(f"API error: {data[:300].decode(errors='replace')}")
        import base64
        return base64.b64decode(b64)
    return data


def img_dims(data):
    import struct
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h, "png"
    # JPEG: scan for SOF0/1/2 marker for dims.
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        m = data[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h, "jpeg"
        if m in (0xD8, 0xD9) or (0xD0 <= m <= 0xD7) or m == 0x01:
            i += 2
            continue
        ln = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + ln
    return 0, 0, "bin"


def png_dims(data):
    w, h, _ = img_dims(data)
    return w, h


def main():
    token = os.environ.get("CF_API_TOKEN", "")
    acct = os.environ.get("CF_ACCOUNT_ID", "")
    if not token or not acct:
        print("REFUSING: CF_API_TOKEN/CF_ACCOUNT_ID not in environment "
              "(source /root/.r2-env).", file=sys.stderr)
        return 2
    want = [a for a in sys.argv[1:] if not a.startswith("-")]
    shots = [(s, p) for s, p in SHOTS if not want or s in want]
    if not shots:
        print(f"no shots match {want}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    ok, fail = 0, []
    for i, (shot, prompt) in enumerate(shots):
        try:
            img = gen(prompt, token, acct)
            w, h, fmt = img_dims(img)
            (OUT / f"{shot}.{fmt if fmt != 'bin' else 'img'}").write_bytes(img)
            (OUT / f"{shot}.json").write_text(json.dumps({
                "shot": shot, "model": MODEL, "file": f"{shot}.{fmt}",
                "width": w, "height": h,
                "prompt": prompt, "cost": "$0 (CF neurons)",
                "generated_at": now, "status": "draft-unreviewed",
                # Atlas anchor eligibility (official image-input rules +
                # SHELL rule): ONLY bare-shell frames anchor. Dressed frames
                # (mic, furniture, curtains) are composition previews.
                "anchor_eligible": shot.startswith("shell-"),
            }, indent=2) + "\n")
            print(f"OK {shot} ({len(img)//1024}KB)")
            ok += 1
        except Exception as e:
            print(f"FAIL {shot}: {e}")
            fail.append(shot)
    print(f"\n{ok}/12 saved to static/concepts/ — $0 spent.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
