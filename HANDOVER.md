# HANDOVER — freaktown, 2026-09-11 final (session closed)

Owner's goal: **avatar flow working** — prompt → custom avatar + minute,
shareable, dad makes his own. **Status: LIVE.**

## Live (all verified with curl)

- **Show:** `https://trial.freak.town` (named tunnel `freaktown-trial` +
  DNS, survives restarts). Flask on this VPS :8090, venv
  `/home/ubuntu/.venvs/freaktown`, env in gitignored `.env` (600).
- **Demo sets:** `/f/brenda-37659b` (AI sad-fat-monkey minute, BASIC monkey
  body) · `/f/todd-4e8ccd` (AI roast-reply with audio + body) ·
  `/f/dad-demo-001` (VRM body, 18 expressions, visemes).
- **AI minutes work for all visitors** (`/api/respond` via CF Workers AI).
  TTS keyless (edge-tts), espeak + ffmpeg installed.
- **Edge worker:** `https://freak-town.tradesprior.workers.dev` (API +
  EpisodeRoom, placeholder page — NOT the show).
- **Pogtown API (Docker :8787):** Postgres, gates green (healthcheck,
  attacker 15/15, npm 67/67).

## Pushed

- pogtown `main`: CP0 (163ff2f). freaktown `trial/avatar-flow` (branch,
  main frozen). Nothing else pending push; trees staged-clean.

## Built this session (all pushed except where noted)

face_profiles.py (8 profiles + POG_FACE_V1) · VRM expression sniffing ·
monkey lane (BASIC preset + species) · NORTHSTAR.md · docs/{BOUNDARIES
(merged), README index, TRIAL_STAGE1_PLAN, avataroptions.md,
vendors/bithuman+runway} · archive/ (dormant engine, git mv) ·
edge/{package.json, .gitignore} + validateCameraCut fix (worker deploys) ·
AGENTS.md + this HANDOVER · pogtown attacker-gate + fetch-upstreams fixes ·
`.cache/upstreams/` × 8 · SFT rescue `/home/ubuntu/data/sft/` · Kaggle pack
`/home/ubuntu/kaggle-walkouts/` (validated, unfired).

## Still needs human (nothing code-side outstanding)

1. **Rotate pasted secrets** (GH PAT + CF/R2 keys went through chat; used
   env-only, on disk only in 600 files: `freaktown/.env`,
   `~/.cloudflared/`).
2. **Vault grant** for opencode (`set-role ... member --vault oracle/main`)
   → unlocks Kaggle kernel firing + secret reads without chat pastes.
3. **three.ws / MetaPerson accounts** for upgraded bodies (BASIC + upload
   carry the demo; northstar bake-off queued).
4. **Push auth done via pasted PAT** — replace with deploy key when convenient.
5. Optional: `chatgpt-right` seat rename (trademark; touches 2 repos +
   treaty test — defer deliberately).

## Traps

test_party.py = script, never pytest. Flask runs from venv (needs `.env`
sourced). Tunnel/DNS/token all exist; recreating = tunnel create + DNS +
config. `freaks/*` gitignored. Quick-tunnel (trycloudflare) may still be
alive — named tunnel is canonical, kill the quick one on sight.
