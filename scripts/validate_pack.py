#!/usr/bin/env python3
"""Validate a freak character pack against the v1 contract.

Usage:
  python scripts/validate_pack.py freaks/<slug>

Checks (exit non-zero with reasons on failure):
  1. character.json parses, has name
  2. avatar.vrm present -> avatar.json present + valid contract shape
  3. delivery.json present -> v1 version, beats have text, expression/
     gesture values inside the editor vocabularies
  4. set.wav present -> valid WAV header
  5. meta.json hashes match files when status is ready/queued/performed
"""

import hashlib
import json
import struct
import sys
from pathlib import Path

FACES = {"neutral", "deadpan", "grin", "annoyed", "confused", "surprised"}
BODIES = {"normal", "hold still", "lean in", "look left", "look right",
          "shrug", "small gesture", "big gesture"}
READY_STATES = {"ready", "queued", "performed"}


def fail(reasons: list[str], msg: str) -> None:
    reasons.append(msg)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_pack.py freaks/<slug>")
        return 2
    root = Path(sys.argv[1])
    reasons: list[str] = []
    if not root.is_dir():
        print(f"FAIL: not a directory: {root}")
        return 1

    def load(name: str):
        p = root / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except Exception as e:
            fail(reasons, f"{name}: invalid JSON ({e})")
            return None

    # 1. character.json
    char = load("character.json")
    if char is None:
        fail(reasons, "character.json: missing")
    elif not isinstance(char.get("name"), str) or not char["name"].strip():
        fail(reasons, "character.json: name required")
    actions = (char or {}).get("actions", {}) or {}
    for aname, a in actions.items():
        if not isinstance(a, dict) or "trigger" not in a or "fallback" not in a:
            fail(reasons, f"actions.{aname}: needs trigger + fallback")
        if isinstance(a, dict) and a.get("face") not in FACES | {None}:
            if a.get("face") is not None:
                fail(reasons, f"actions.{aname}: face '{a.get('face')}' outside vocabulary")
        if isinstance(a, dict) and a.get("body") not in BODIES | {None}:
            if a.get("body") is not None:
                fail(reasons, f"actions.{aname}: body '{a.get('body')}' outside vocabulary")

    # 2. avatar contract
    has_vrm = (root / "avatar.vrm").exists() or (root / "avatar.glb").exists()
    avatar = load("avatar.json")
    if has_vrm and avatar is None:
        fail(reasons, "avatar.json: required when avatar.vrm/.glb present")
    if avatar is not None:
        caps = avatar.get("capabilities", {})
        for key in ("humanoid", "blink", "visemes", "look_at", "expressions"):
            if key not in caps:
                fail(reasons, f"avatar.json: capabilities.{key} missing")
        asset = avatar.get("asset", "")
        if asset and not (root / asset).exists():
            fail(reasons, f"avatar.json: asset '{asset}' not found in pack")

    # 3. delivery.json
    delivery = load("delivery.json")
    if delivery is not None:
        if delivery.get("version") != "freaktown.delivery.v1":
            fail(reasons, "delivery.json: version must be freaktown.delivery.v1")
        for b in delivery.get("beats", []):
            if not isinstance(b.get("text"), str) or not b["text"].strip():
                fail(reasons, f"delivery beats {b.get('id', '?')}: text required")
            perf = b.get("performance", {}) or {}
            if "expression" in perf and perf["expression"] not in FACES:
                fail(reasons, f"beat {b.get('id')}: expression outside vocabulary")
            if "gesture" in perf and perf["gesture"] not in BODIES:
                fail(reasons, f"beat {b.get('id')}: gesture outside vocabulary")

    # 4. set.wav header
    wav = root / "set.wav"
    if wav.exists():
        try:
            with open(wav, "rb") as f:
                riff, _, wave = struct.unpack("<4sI4s", f.read(12))
            if riff != b"RIFF" or wave != b"WAVE":
                fail(reasons, "set.wav: not a valid WAV file")
        except Exception as e:
            fail(reasons, f"set.wav: unreadable ({e})")

    # 5. meta hashes for submittable packs
    meta = load("meta.json")
    if meta is not None and meta.get("status") in READY_STATES:
        files = meta.get("files", {})
        for fname, recorded in files.items():
            p = root / fname
            if not p.exists():
                fail(reasons, f"meta: '{fname}' recorded but missing")
                continue
            actual = "sha256:" + hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != recorded:
                fail(reasons, f"meta: '{fname}' hash mismatch (stale or tampered)")

    if reasons:
        print(f"FAIL: {root}")
        for r in reasons:
            print(f"  - {r}")
        return 1
    print(f"OK: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
