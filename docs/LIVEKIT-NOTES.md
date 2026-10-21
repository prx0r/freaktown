# LIVEKIT — self-hosted rooms + the live half of the Delivery SDK

> Session 2026-10-22. Server + adapter + live test all green. Companion:
> `docs/DELIVERY-SDK.md` (rendered half), `docs/LIVE-STAGE*.md` (stage).

## What it is for us (one sentence)

The **ears-and-mouths layer**: humans and agents talking over live mics in
one room (podcast/interview/party voice), with barge-in handled. It does NOT
replace the stage (three.js), party game logic (`party.py`), or sealed sets —
those stay ours. Analogy: our hand-rolled monitor WebRTC scales to ~6 faces;
LiveKit is the proper SFU under it.

## Server (free, Apache-2.0, self-hosted — no cloud account)

- Binary: `livekit-server v1.13.10` at `/usr/local/bin/livekit-server`
  (18.5MB tarball from github.com/livekit/livekit releases).
- Config: `/root/.livekit/server.yaml` (600, **outside git — keys live
  there**): port 7880, rtc UDP 50000-60000, `keys: {<key-name>: <secret>}`.
- Keys ALSO in freaktown `.env` (600): `LIVEKIT_API_KEY` (the key NAME),
  `LIVEKIT_API_SECRET`, `LIVEKIT_URL=ws://127.0.0.1:7880`.
- Service: `systemctl {status,restart} livekit` (unit `livekit.service`).
  Health: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:7880/` → 200.

### Gotchas learned the hard way (don't rediscover)
1. **`bind_addresses: []` breaks startup** on this box ("could not start
   server") — omit the key entirely (binds all interfaces).
2. **`keys:` is a FLAT MAP of `key-name: secret`** — not fields. Every
   *value* must be ≥32 chars (a value named literally `api-key` with 19
   chars = the "secret too short" error). Clients pass the NAME as their
   api_key.
3. **Register before creating rooms**: auto-dispatch only assigns jobs to
   rooms created AFTER the worker registers (`worker_registered` event).
   Creating the room first = agent never joins.
4. `pip install livekit-agents…[mcp]` pulls `mcp>=2.2` which BREAKS quill
   MCP (needs 1.29.0). Pinned back — don't upgrade mcp casually.

## The adapter: `scripts/delivery_agent.py`

Characters2 character → LiveKit agent, all $0 lanes:

| slot | source |
|---|---|
| brain | `qwen-flash-character` via Qwen workspace compatible-mode |
| voice | Fish `s2.1-pro-free` (`fishaudio.TTS`, `normalize=False` keeps drama tags) |
| ears | silero VAD (local, `livekit.agents.inference.VAD`) |
| persona | `characters2/freaks/<slug>/character.json` → instructions |

```bash
/usr/bin/python3 scripts/delivery_agent.py                    # default Ralph
/usr/bin/python3 scripts/delivery_agent.py --character gnorma-the-hoa-gnome
```

**Test result (2026-10-22)**: worker registered → room created → agent joined
(`agent-*`) → 600+ audio frames to subscriber → transcript verbatim in
character: *"Welcome to bloodline management, folks…"* → **PASS**.

## Plugin verdicts (full pass over ~90; see session notes)

Shipped here: `openai` (Qwen via base_url), `fishaudio`, `silero`,
`typesafe` (Jev), `sarvam` (Hindi), `gradium` (Phonon). Ruled out by prior
decisions: `spatius`, `inworld` (metered). Paid voice clouds skipped ($0).
`turn-detector` plugin deprecated → `livekit.agents.inference.TurnDetector`.

## Costs

Self-host server: $0 (infra only; ~50-150MB RAM — box has headroom).
LiveKit Cloud "Build" tier is also $0 if ever wanted (1,000 agent-min +
5,000 WebRTC-min + 50GB/mo, no card) — NOT used; server is local.

## Next seams (not built)

- Podcast **events** (room + dispatch + multi-agent) → LIVE-STAGE-EXTENDING §4
- Party ↔ LiveKit voice bridge (party.py stays text; voice joins later)
- Public access needs tunnel/UDP open (server binds all; UFW currently
  22+80+8090 — UDP 50000-60000 would need opening for off-box WebRTC)
