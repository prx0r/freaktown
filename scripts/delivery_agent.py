#!/usr/bin/env python3
"""delivery_agent.py — characters2 character → LiveKit room (voice, live).

THE ADAPTER: takes a Delivery-SDK-side character (character.json + voice) and
runs it as a LiveKit agent — the live half of the Delivery SDK contract
(docs/DELIVERY-SDK.md): sealed-set.v1 stays the RENDERED half (stage), this
is the TALKING half (podcast/interview rooms). Same character, same Fish
voice, both planes.

  plane        carrier                     timing
  ----------   --------------------------  --------------------------
  rendered     sealed-set.v1 → setAdapter  delivery-authoritative ms
  LIVE (this)  LiveKit agent session       turn detection (silero VAD)

Wiring (all $0 lanes):
  voice   → fishaudio.TTS(model="s2.1-pro-free", voice_id=…)
  brain   → openai.LLM(base_url=Qwen workspace compatible-mode)
  ears    → livekit.agents.inference.VAD("silero")  (local)
  persona → character.json (name/deal/facts) as instructions

Server: self-hosted livekit-server (systemd `livekit`), keys in freaktown
.env (600, never git). Auto-dispatch: any room created gets this worker.

Run:  /usr/bin/python3 scripts/delivery_agent.py [--character SLUG] [--room NAME]
Test: creates the room, the worker joins, generates one in-character line,
      a subscriber counts the audio frames. PASS/FAIL + exit code.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

# repo .env first (owner's config overrides shell) — same rule everywhere
for _line in (BASE / ".env").read_text().splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

from livekit import api as lkapi, rtc  # noqa: E402
from livekit.agents import Agent, AgentServer, AgentSession, JobContext  # noqa: E402
from livekit.agents import inference  # noqa: E402
from livekit.plugins import fishaudio, openai as lk_openai  # noqa: E402

CHARACTERS2 = Path(os.environ.get("SHOW_PERFORMERS_DIR", "/root/characters2/freaks"))
LIVEKIT_URL = os.environ.get("LIVEKIT_URL", "ws://127.0.0.1:7880")
LK_KEY = os.environ.get("LIVEKIT_API_KEY", "")
LK_SECRET = os.environ.get("LIVEKIT_API_SECRET", "")

server = AgentServer()
CONFIG: dict = {}   # set in __main__ before server.run(); inherited by forkserver jobs


def persona_instructions(slug: str) -> str:
    try:
        ch = json.loads((CHARACTERS2 / slug / "character.json").read_text())
    except (OSError, ValueError) as e:
        raise SystemExit(f"character not found: {slug} ({e})")
    name = ch.get("name", slug)
    p = ch.get("persona", {}) or {}
    facts = "; ".join(str(f) for f in (p.get("facts") or [])[:6])
    return (
        f"You are {name}. {p.get('deal', '')} Facts: {facts} "
        f"You are ON A LIVE STAGE mic (podcast/room), talking with others now. "
        f"Stay in character in every reply, one or two short sentences. "
        f"Never mention being an AI."
    )


@server.rtc_session()
async def entrypoint(ctx: JobContext):
    slug = CONFIG.get("character", "reptilian-ralph-middle-management")
    await ctx.connect()
    session = AgentSession(
        vad=inference.VAD(model="silero"),
        llm=lk_openai.LLM(
            model=os.environ.get("LIVEKIT_LLM_MODEL", "qwen-flash-character"),
            api_key=os.environ.get("QWEN_API_KEY", ""),
            base_url=os.environ.get("QWEN_BASE_URL", "").rstrip("/") + "/compatible-mode/v1",
        ),
        tts=fishaudio.TTS(
            api_key=os.environ.get("FISH_API_KEY", ""),
            # `| str` accepts our free lane (models.py Literal has no free id)
            model="s2.1-pro-free",
            voice_id=CONFIG.get("voice") or None,
            normalize=False,          # keep Fish inline drama tags intact
        ),
    )
    await session.start(agent=Agent(instructions=persona_instructions(slug)), room=ctx.room)
    print(f"[job] session started in room={ctx.room.name}", flush=True)
    said: list[str] = []

    @session.on("conversation_item_added")
    def _item(ev):                      # capture what the character actually says
        item = getattr(ev, "item", None)
        if item is not None and getattr(item, "role", "") == "assistant":
            said.append(str(getattr(item, "content", "") or getattr(item, "text", ""))[:240])

    speech = await session.generate_reply(
        instructions="You just got on mic. Say ONE short in-character line "
                     "greeting the room."
    )
    try:
        await asyncio.wait_for(speech.wait_for_playout(), timeout=30)
    except (asyncio.TimeoutError, TimeoutError):
        pass
    print(f"[job] AGENT_SAID: {said[-1] if said else '(no transcript captured)'}", flush=True)
    await asyncio.sleep(4)   # subscribers drain, then job ends


async def probe(room_name: str, timeout_s: float = 90.0) -> dict:
    """Create the room, subscribe, wait for the agent's audio frames."""
    lc = lkapi.LiveKitAPI(LIVEKIT_URL, LK_KEY, LK_SECRET)
    stats = {"frames": 0, "agent": None, "tracks": [], "created": False}
    try:
        await lc.room.create_room(lkapi.CreateRoomRequest(name=room_name, empty_timeout=120))
        stats["created"] = True

        token = (lkapi.AccessToken(LK_KEY, LK_SECRET)
                 .with_identity("delivery-probe").with_name("Probe")
                 .with_grants(lkapi.VideoGrants(room_join=True, room=room_name))).to_jwt()

        room = rtc.Room()

        @room.on("participant_connected")
        def _pc(p: rtc.Participant):
            stats["agent"] = p.identity
            print(f"[probe] participant joined: {p.identity}", flush=True)

        @room.on("track_subscribed")
        def _ts(track, *_):
            stats["tracks"].append(getattr(track, "kind", "?"))
            if isinstance(track, rtc.RemoteAudioTrack):
                async def _count():
                    stream = rtc.AudioStream(track)
                    async for _frame in stream:
                        stats["frames"] += 1
                asyncio.ensure_future(_count())

        await room.connect(LIVEKIT_URL, token)
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            if stats["frames"] > 0:
                break
            await asyncio.sleep(0.25)
        # grace: let the job finish its utterance so [job] AGENT_SAID prints
        await asyncio.sleep(6)
        return stats
    finally:
        try:
            await lc.aclose()
        except Exception:
            pass


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--character", default="reptilian-ralph-middle-management")
    ap.add_argument("--voice", default=os.environ.get("DELIVERY_VOICE", ""))
    ap.add_argument("--room", default="delivery-agent-test")
    args = ap.parse_args()
    CONFIG.update(character=args.character, voice=args.voice)

    if not all((LK_KEY, LK_SECRET, os.environ.get("QWEN_API_KEY"), os.environ.get("FISH_API_KEY"))):
        print("FAIL: missing LIVEKIT_*/QWEN_*/FISH_* keys in .env")
        return 2

    # worker (auto-dispatch: only rooms created AFTER registration get jobs)
    registered = asyncio.Event()
    server.on("worker_registered", lambda *a: registered.set())
    worker_task = asyncio.create_task(server.run())
    try:
        # registration took ~2.5s live — creating the room first lost the race
        await asyncio.wait_for(registered.wait(), timeout=25)
    except (asyncio.TimeoutError, TimeoutError):
        print(f"FAIL: worker never registered (done={worker_task.done()}, "
              f"exc={worker_task.exception()!r})")
        return 3
    print("[main] worker registered — creating room now", flush=True)
    if worker_task.done():   # crashed after registering
        print(f"FAIL: worker died: {worker_task.exception()!r}")
        return 3

    stats = await probe(args.room)
    ok = stats["frames"] > 0 and stats["agent"]
    print("\n=== RESULT ===")
    print(f"  room created : {stats['created']}")
    print(f"  agent joined : {stats['agent']}")
    print(f"  audio frames : {stats['frames']}  (subscriber)")
    print(f"  tracks       : {stats['tracks']}")
    print(f"  verdict      : {'PASS' if ok else 'FAIL'}")
    worker_task.cancel()
    return 0 if ok else 1


if __name__ == "__main__":
    rc = asyncio.run(main())
    sys.exit(rc)
