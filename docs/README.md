# docs/ index

Start here: `BOUNDARIES.md` (what lives where) → `../ARCHITECTURE.md`
(prod truth) → `../devplan.md` (migration plan, long).

| Doc | Answers |
|---|---|
| `BOUNDARIES.md` | pogtown vs freaktown, new vs old, rooms, asset rule, hard rules |
| `TRIAL_STAGE1_PLAN.md` | Stage 1 trial: prompt → minute (PLAN ONLY, unexecuted) |
| `HANDOFF_STABLE_AUDIO.md` | Stable Audio Open Small: weights access, prompt compiler, cache contract, dead ends |
| `CHARACTER_PACK.md` | character bundle format (full contract) |
| `JUDGE_VOICES.md` | Ella/judge voice catalog |
| `PRELAUNCH-HARDENING.md` | freak.town edge hardening (P0 applied 2026-09-09) |
| `avataroptions.md` | ownable-avatar bake-off research (Avatar SDK, Threedium, Neural4D, Meshy, Polywink, TalkingHead, VRM) |
| `vendors/bithuman.md` | bitHuman API/models/pricing/LiveKit plugin brief |
| `vendors/runway.md` | Runway models/API/pricing + $0.20 price-check flag |
| `migration/KILLELLA_IMPORT.md` | killella donor merge record (frozen repo, ancestry only) |

Code map: serving = `app.py` + `party.py`; future backend = `backend/`;
live/edge = `apps/live/` + `edge/worker/`; renderer = `packages/stage-runtime/`;
schemas = `contracts/`; retired engine = `archive/` (see its README).
