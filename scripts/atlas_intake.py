#!/usr/bin/env python3
"""Vendor GLB intake: Atlas/Meshy/Mixamo output → sniffer + face battery → upload.

Usage:
  scripts/atlas_intake.py <path-or-url.glb> [--slug badger-002 --from badger-001 --upload]

- No keys, no vendor calls. Bytes in, verdict out.
- --upload clones bundle --from (beats/audio/character) under --slug, then
  POSTs the GLB to /api/avatar/upload via an in-process test client and
  checks preload + watch/AR/record routes. Nothing is committed or pushed.

Exit 0 = intake clean (rigged and web-sized, or report printed without --upload).
Exit 2 = STATIC mesh (no skeleton) or oversize — still uploadable, puppet mode covers it.
"""

import argparse
import io
import json
import shutil
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

WEB_BUDGET = 8 * 1024 * 1024


def load_bytes(src: str) -> bytes:
    if src.startswith(("http://", "https://")):
        req = urllib.request.Request(src, headers={"User-Agent": "freaktown-intake/1"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read(60 * 1024 * 1024 + 1)
    return Path(src).read_bytes()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("glb", help="local path or http(s) URL to .glb")
    ap.add_argument("--slug", default="", help="new freak slug for --upload")
    ap.add_argument("--from", dest="clone", default="badger-001",
                    help="bundle to clone beats/audio/character from")
    ap.add_argument("--upload", action="store_true")
    args = ap.parse_args()

    from app import _sniff_glb
    from face_profiles import to_pog_face

    blob = load_bytes(args.glb)
    print(f"bytes: {len(blob) / 1e6:.1f}MB magic={blob[0:4]!r}")
    if blob[0:4] != b"glTF":
        print("NOT a glb binary — refusing.")
        return 2

    caps = _sniff_glb(blob)
    face = to_pog_face(caps.get("all_morph_names", []), "glb")
    print(f"rigged={caps['rigged']} joints={caps['joint_count']} "
          f"skin={caps['has_skin']} morphs={caps['facial_morphs']} "
          f"lipsync={caps['lipsync']} {caps.get('lipsync_profile')}")
    print(f"face_profile={face['profile']} intents={len(face['intents'])}")
    names = caps.get("morph_names") or []
    if names:
        print("morph_names[:12]:", names[:12])

    static = not caps["rigged"]
    oversize = len(blob) > WEB_BUDGET
    if oversize:
        print(f"OVERSIZE for web — simplify to <8MB first "
              f"(gltf-transform simplify --ratio ~0.05).")
    if static:
        print("STATIC mesh — puppet mode covers it; bones need Atlas Rig/Mixamo pass.")

    if not args.upload:
        return 2 if (static or oversize) else 0
    if not args.slug:
        print("--upload needs --slug")
        return 2
    if static or oversize:
        print("uploading anyway (--upload forces it).")

    from app import FREAK_DIR, app
    src = FREAK_DIR / args.clone
    dst = FREAK_DIR / args.slug
    if dst.exists():
        print(f"{dst} exists — refusing to overwrite.")
        return 2
    dst.mkdir()
    for f in ("character.json", "delivery.json", "meta.json", "offsets.json", "set.wav"):
        if (src / f).exists():
            shutil.copy(src / f, dst / f)
    c = app.test_client()
    r = c.post("/api/avatar/upload",
               data={"slug": args.slug,
                     "file": (io.BytesIO(blob), "intake.glb")},
               content_type="multipart/form-data").get_json()
    print("UPLOAD:", r.get("ok"), r.get("avatar_url") or r.get("error"))
    if not r.get("ok"):
        return 2
    p = c.get(f"/api/preload/{args.slug}").get_json()
    print("PRELOAD:", p.get("avatarUrl"), "|", p.get("face_profile"))
    for u in (f"/f/{args.slug}", f"/a/{args.slug}", f"/r/{args.slug}"):
        print(u, c.get(u).status_code)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
