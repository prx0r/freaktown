# Boundaries

```text
Freak Town Studio creates performances.

Contracts describe performances.

FastAPI stores and indexes performances.

EpisodeRoom coordinates live performances.

StageRuntime renders performances.

Ella observes and acts on live events.

No subsystem may recreate another subsystem's responsibility.
```

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
