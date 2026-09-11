# Boundaries — what lives where (2026-09-11)

```text
Freak Town Studio creates performances.

Contracts describe performances.

FastAPI stores and indexes performances.

EpisodeRoom coordinates live performances.

StageRuntime renders performances.

Ella observes and acts on live events.

No subsystem may recreate another subsystem's responsibility.
```

## 0. Pogtown vs Freaktown (repo line)

| | prx0r/pogtown | prx0r/freaktown (this repo) |
|---|---|---|
| Owns | game truth: packs, runtime, protocol, rooms API, director, sealed-bundle import | product: Studio, stage, party UX, media, performance contracts |
| Serves | Pog API (Docker, Postgres) | Flask app (live site), later FastAPI strangler |
| Never | product UI, media, TTS, avatars | game-truth reimplementation (see `archive/`) |

Import direction: freaktown consumes the pog protocol via the stage-adapter
(pog side) and `backend/services/freaktown/`. Pogtown never imports freaktown
runtime code — only validates its bundles. The dormant Python game engine was
archived for exactly this reason (`archive/README.md`).

## 1. New vs old (in this repo)

- **Serving now:** `app.py` (Flask, strangler shell) + `party.py` blueprint +
  `contracts/` + `freaks/` bundles + `stage/` + `apps/live/` + `edge/worker/`
  + `packages/stage-runtime/`.
- **Future, not serving:** `backend/` (FastAPI + Postgres + R2 interfaces).
  Do not route traffic to it until parity is proven; do not add a second
  Studio/watch/party implementation inside it (devplan §2).
- **Retired:** `archive/` (dormant Python game engine — authority moved to
  pogtown), killella donor history (git ancestry only, repo frozen).

## 2. The three "rooms" (do not merge)

- **Pog rooms** (pogtown): authoritative game sessions, all formats.
- **PartyRoom** (`party.py`): small invited groups, secret roles, turn-based
  party games. Stays — different semantics from broadcast (devplan §16).
- **EpisodeRoom** (`edge/worker/episode-room.ts`): live broadcast show state.

## 3. Asset rule (avatars/media)

Canonical bodies are open files (GLB/VRM + `avatar.json` manifest) in R2,
referenced by the Freak Pack. Vendors (three.ws forge, bitHuman, Runway) are
providers behind the manifest — never the store of record. See
`docs/avataroptions.md`, `docs/vendors/`.

## Ownership

| Concern | Owner | Lives in |
|---|---|---|
| Product behavior, Studio, watch/respond, party, URLs, lore, Ella character | Freak Town | `app.py` (temp), `party.py` (temp), `static/`, `ella_*.md` |
| Schema authority | Contracts | `contracts/*.schema.json` + `contracts/fixtures/golden-freak-v1/` |
| Persistence, intake, judges, media metadata | FastAPI backend | `backend/` |
| Live coordination | EpisodeRoom (DO) | `edge/worker/` |
| Rendering (audio/avatar/camera) | StageRuntime | `packages/stage-runtime/` |
| Ella execution | Ella runtime | `backend/services/ella/`, `edge/worker/ella/` |

## Hard rules

- One Studio (Freak Town). No Green Room, no Dressing Room API.
- One delivery schema version in force (`freaktown.delivery.v1`, frozen).
- Intake validates/hashes/stores; never rewrites creative content.
- Postgres = durable truth. R2 = immutable assets. DO = live state only.
- D1 rows (edge auth) are provisionally authoritative debt, not pattern.
- No x402/crypto in the MVP runtime. No second business database.
- `app.py`/`party.py` die by strangler extraction, not rewrite.
