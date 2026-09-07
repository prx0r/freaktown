#!/usr/bin/env python3
"""Render every cast member's minute to audio for posting.

Usage:
  python scripts/render_cast.py              # all 19
  python scripts/render_cast.py r2d2 glados  # specific slugs

Output: audio_output/cast/<slug>.mp3
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comedians import ALL_CAST

OUT = Path(__file__).resolve().parent.parent / "audio_output" / "cast"
OUT.mkdir(parents=True, exist_ok=True)


async def render_one(c: dict, retries: int = 4) -> Path:
    import asyncio as _asyncio
    import edge_tts
    out = OUT / f"{c['slug']}.mp3"
    if out.exists() and out.stat().st_size > 0:
        return out
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            await edge_tts.Communicate(c["minute"], c.get("voice", "en-US-AriaNeural")).save(str(out))
            if out.stat().st_size > 0:
                return out
        except Exception as e:
            last_err = e
            await _asyncio.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{c['slug']} ({c.get('voice')}): {last_err}")


async def main(slugs: list[str] | None):
    import edge_tts  # noqa: F401 — fail fast if TTS unavailable
    import asyncio as _asyncio
    targets = [c for c in ALL_CAST if not slugs or c["slug"] in slugs]
    for c in targets:
        out = await render_one(c)
        words = len(c["minute"].split())
        print(f"  {c['slug']:<22} {words:>3}w  {out.name}  ({out.stat().st_size // 1024}KB)", flush=True)
        await _asyncio.sleep(1)


if __name__ == "__main__":
    slugs = sys.argv[1:] or None
    print(f"Rendering {len(slugs) if slugs else len(ALL_CAST)} sets...")
    asyncio.run(main(slugs))
    print("Done.")
