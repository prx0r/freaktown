# AGENTS.md — funnier

New agent: read in order: `docs/STATUS.md` (honest vision/done/not-done/theatre/next — start here), then `HANDOVER-2026-10-17.md` (latest: stage day), then `docs/BOUNDARIES.md` (what lives where), then this file. Do not build until you have read all four. `HANDOVER-2026-09-12.md` is STALE — do not treat it as latest.

## What funnier owns

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
funnier = product, studio, avatar pipeline, performance contracts,
delivery, Ella, the live site.
Shared key = the freak pack identity. Server is truth.

Gift packs: pogtown owns the spec and state machine. funnier generates
the portrait, video, voice, and walkout. Nothing crosses the boundary
except bundles and events.

## Binding rules

1. **Secrets in vault/env, never in tree, never in chat.** Before every
   commit the secret-scan must print nothing:
   `grep -rIlE "cfat""_|ghp""_|sk-[A-Za-z0-9]{10,}" --exclude-dir=.git .`
   (split-quoted so this file doesn't self-match; shell concatenates it to
   the real pattern). Vault reads need `member` role; proxy role only wraps
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

## Live status (verified 2026-10-16, honest)

- Box: systemd `freaktown.service` active, `/usr/bin/python3`, PORT 8090.
  There is NO venv on this box (`/home/ubuntu/.venvs/freaktown` is gone —
  do not source it). System python runs the service.
- On-box: `http://127.0.0.1:8090/play` → 200. `http://127.0.0.1:8090/party` → 404 (no such route — Flask home is `/play`).
- Public: `https://party.funnier.si/play` → 200 (direct Caddy+TLS, works).
  `https://www.funnier.si/party` and `/play` → currently 404 (Worker `funnier-web` `/party`→`/play` mapping is broken — do NOT claim the www URL is live until you curl it yourself).
- Missing runtime: no `.env` on disk (Ella LLM dead until restored), no `data/` dir (persistence restarts empty). `party_rooms.json` / `party_records.json` / `party_events.jsonl` exist but are gitignored runtime state.
- Canon lives in `/root/improv/docs/`: `PARTY-FORMATS.md` (12 modes, 19+ formats), `ENGINES.md` (E1–E12), `MVP-FREEZE-NIGHT-V1.md`. Only 3 modes are wired in `party.py`.

## Where things are

`docs/STATUS.md` (honest state — read first) · `HANDOVER-2026-10-21.md` (latest: show runtime + chatter) · `NORTHSTAR.md` (avatar doctrine) · `docs/` (map in `docs/README.md`) · `docs/FACE-VOICE-REACT.md` (face/viseme/AU stack) · `docs/DIRECTOR-VOCAB.md` (cue vocabulary) · `docs/NEWSROOM-SDK.md` (rundown→show) · `docs/LIVEKIT-NOTES.md` (self-hosted rooms + delivery→agent adapter) · `party.py` (party game — the live multiplayer loop) · `cauldron_show.py` (Cauldron show backend — phases/laugh-track/interview) · `party_chatter.py` (proactive table talk) · `lab.py` (tech-lab rigs only, never called by game) · `comedy/` (theory engine — currently NEVER imported by `party.py`) · `game-packs/freeze-night-v1.freak-game.json` (pack spec — currently NEVER loaded by `party.py`, hardcoded `FZ_ROUNDS` rules instead) · `static/smile-referee.js` + `static/affect-servo.js` (served by lab only, no `<script>` tag in stage/controller) · `backend/services/` (delivery, audio, ella, judge, scoring) · `contracts/` (schema authority) · `packages/newsroom/` (news rundowns → directed news-studio shows: `docs/NEWSROOM-SDK.md`) · `packages/stage-runtime/` (live performer) · `edge/worker/` (episode room + ella live) · `apps/live/` (web client; live stage: `docs/LIVE-STAGE.md`, `docs/LIVE-STAGE-EXTENDING.md`) · `freaks/` (bundle storage, gitignored) · `archive/` (retired engine, read-only).

## Commands

```bash
/usr/bin/python3 test_allbots.py && /usr/bin/python3 test_freeze_night.py && /usr/bin/python3 test_party.py && /usr/bin/python3 test_stone_face.py
/usr/bin/python3 test_quip_clash.py && /usr/bin/python3 test_solo_night.py && /usr/bin/python3 test_tech_lab.py && /usr/bin/python3 test_poker.py
/usr/bin/python3 test_show.py && /usr/bin/python3 test_chatter.py && /usr/bin/python3 test_funnier_skin.py
/usr/bin/python3 scripts/delivery_agent.py    # LiveKit live voice E2E (server: systemctl status livekit)
pytest tests/contract -q      # contract suite (1 pre-existing env failure: livekit not installed)
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/play   # on-box check
curl -s -o /dev/null -w "%{http_code}\n" https://party.funnier.si/play # public check
npm install && npm test       # TS workspace (contracts, stage-runtime, apps/live, edge logic)
npm run build                 # apps/live/dist (static live stage)
```

## Theatre warnings (do not claim these work until you verify)

1. `comedy/` does not drive the game. Zero imports in `party.py` — no pregate→director→delivery chain, no vetoes, no priors in scoring.
2. The game-pack JSON is not loaded. `_fz_next_round` uses hardcoded `FZ_ROUNDS`; pack drift is real (min players 3 vs 4, no SCENE/HALFTIME/CROWNING, 8-seg wheel vs canon 12).
3. Affect/smile/props rigs are lab-only. `lab.py` validator + `affect-servo.js` vote weights + `smile-referee.js` are never called by `party.py` tallies.
4. Bots drive freeze-night + quip only. No bot driver for roast-relay / freaktionary (`test_allbots.py` skips them by design).
5. Controller could not send callbacks or caught-that until the 2026-10-16 fix (callback textarea + I-CAUGHT-THAT button). Server API existed; UI did not.
6. `test_jev_images` / `test_affect_parity` cited in the 10-16 handover do not exist in-tree — do not cite them as coverage.
7. Game-truth boundary is aspirational, not enforced. This repo says "game truth lives in pogtown" but `party.py` IS a full game implementation (rooms, rounds, ballots, bots). Treat the boundary doc as intent, not fact.

## Known failures

`test_livekit.py` fails because `livekit` module is not installed in the
venv. This is an environmental dependency, not a code bug. Do not mark it
as broken without installing the module first.
