# AGENTS.md — freaktown

New agent: read in order: `HANDOVER-2026-09-12.md` (latest state), then
`docs/BOUNDARIES.md` (what lives where), then this file. Do not build until
you have read all three.

## What freaktown owns

Product and stage. The live site, studio, party UX, performance contracts,
the full avatar pipeline (face profiles, VRM, takes, revoice, walkout, record
modes, Blender factory, intake), voice bank, Ella as character and judge, and
the episode room for live broadcast coordination.

What it does NOT own: game truth. Game state lives in pogtown and is consumed
through an adapter, never reimplemented. The retired Python game engine in
`archive/` is the closed chapter.

## Boundary with pogtown

pogtown = runtime, protocol, rooms API, gift packs, order state machine,
the five gift tools, media providers, channel reference.
freaktown = product, studio, avatar pipeline, performance contracts,
delivery, Ella, the live site.
Shared key = the freak pack identity. Server is truth.

Gift packs: pogtown owns the spec and state machine. freaktown generates
the portrait, video, voice, and walkout. Nothing crosses the boundary
except bundles and events.

## Binding rules

1. **Secrets in vault/env, never in tree, never in chat.** Before every
   commit: `grep -rIlE "cfat_|ghp_|sk-[A-Za-z0-9]{10,}" --exclude-dir=.git .`
   must print nothing. Vault reads need `member` role; proxy role only wraps
   outbound calls.
2. **Never push.** Owner pushes. Commit locally only when asked.
3. **Check the site before claiming a deploy.** `curl` the public URL and the
   real routes (`/f/<slug>`, preload, studio) — a 200 on `/` proves nothing.
   A placeholder page is not a launch; say so loudly if that's all there is.
4. **Strangler, not rewrite.** `app.py`/`party.py` serve live traffic. Extract
   gradually, behavior identical. No second Studio/watch/party implementation
   (see `docs/BOUNDARIES.md` + `devplan.md` §2).
5. **Game truth lives in pogtown.** Never reimplement it here. This repo
   consumes via adapter. The archive is read-only.
6. **Face/rig changes are additive.** New `face_profiles.py` profiles and
   manifest keys only; never rename/remove a field. Sniffer never invents a
   morph name that isn't in the bytes.
7. **Small diffs, tested each step.** Python: `pytest tests/contract -q`
   (1 pre-existing env failure: livekit not configured). Party sim runs as
   script: `python3 test_party.py`, never under pytest.
8. **Kill by exact PID, never pattern-kill.** (`pkill -f app.py` matches your
   own shell. Read `/proc` cmdlines and kill the PID.)
9. **Background servers fight sandboxes.** Prefer in-process Flask test
   client for verification; use tunnels only for public demos.

## Where things are

`HANDOVER-2026-09-12.md` (latest) · `NORTHSTAR.md` (avatar doctrine) ·
`docs/` (index below) · `contracts/` (schema authority) ·
`backend/services/` (delivery, audio, ella, judge, scoring, bundles) ·
`packages/stage-runtime/` (live performer) ·
`edge/worker/` (episode room + ella live) ·
`apps/live/` (web client) ·
`freaks/` (bundle storage, gitignored) ·
`archive/` (retired engine, read-only).

## Commands

```bash
source /home/ubuntu/.venvs/freaktown/bin/activate
pytest tests/contract -q      # contract suite (46/47 pass, 1 env failure)
python3 test_party.py         # party sim (script, never pytest)
python3 app.py                # Flask dev server (live traffic, need .env)
```

## Known failures

`test_livekit.py` fails because `livekit` module is not installed in the
venv. This is an environmental dependency, not a code bug. Do not mark it
as broken without installing the module first.
