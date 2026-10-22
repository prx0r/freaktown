# Meshy API — 3D generation for the stage

Text/image → rigged, animated 3D characters via REST. Used to produce
performer avatars (GLB) for the live stage: generate → rig (+ walk/run) →
drop into `characters3` → stage `loadAvatar` picks it up.

## Auth

Every call: `Authorization: Bearer $MESHY_API_KEY`.
Key lives in `freaktown/.env` as `MESHY_API_KEY` (0600, already there).
Env-var style, same as the rest of `app.py` (`os.getenv`).

Verified live: `GET /openapi/v1/balance` → account holds credits
(614 monthly + 40 permanent at import time).

## Base URL

`https://api.meshy.ai/openapi/v1/<endpoint>`

**Not** `/v1/<endpoint>` — the bare `/v1` path returns
`NoMatchingRoute`. Docs live at `https://docs.meshy.ai`; full OpenAPI
schema vendored at `/tmp/meshy-openapi.json` on the box (179KB, "Meshy
API 1.0.0"). `llms.txt` also exists for agents without MCP support; a
first-party MCP server is documented under `/en/api/ai`.

## The task pattern (everything is async)

1. `POST /openapi/v1/<task>` → `{ "result": "<task-id>" }`
2. `GET /openapi/v1/<task>/<task-id>` until `status` ∈
   `SUCCEEDED | FAILED | CANCELED` (sleep `Retry-After` seconds between polls;
   give it up to ~60 min before recycling the ID).
3. `GET .../stream` gives the same updates over SSE if you prefer push.

Result bodies carry signed `model_urls` (`.glb`, `.fbx`, …) plus
`thumbnail_url`. **Signed URLs and files expire: Meshy keeps results 3
days, then may delete.** Download immediately into the repo or R2.

Failed tasks refund credits; deleting a `FAILED`/`CANCELED` task is free but
pays nothing back; deleting `IN_PROGRESS` is `409` (don't).

## Endpoints that matter here

| Endpoint | Use here |
|---|---|
| `POST /text-to-3d` | Generate a performer from a prompt. Ships Meshy 7 (2026, most detail). |
| `POST /image-to-3d` | Generate a performer from concept art (Meshy 7 keeps likeness). Accepts public `image_url`. |
| `POST /multi-image-to-3d` | Character likeness from several photos (front/side/back). |
| `POST /rigging` | Add a skeleton + bind the mesh, returns rigged GLB/FBX **plus walk + run cycles**. This is what makes a generated extra actually move. |
| `POST /animation`, `/text-to-motion` | Drive a rigged mesh with canned/text motion. |
| `POST /retexture` | Re-skin an existing GLB (seasonal variants, costume swaps) without re-modeling. |
| `POST /convert`, `/remesh`, `/resize` | Format conversion, `target_polycount ≤ 300000`, resizing. |
| `POST /image-to-image`, `/text-to-image` | Concept art upstream of 3D. |
| `POST /print/*` | 3D-print pipeline (analyze/repair/multi-color/split) — merch lane, out of scope for the stage. |
| `GET /balance`, `GET /usage` | Credits and spend. Check before a batch. |

Full list: `GET`-able from the vendored OpenAPI spec (`/tmp/meshy-openapi.json`).

## Rigging (the important one)

Rigged output is what the stage can animate. Rules, from the docs:

- **Humanoids only** — bipeds with clear limbs. Non-humanoids return `422`
  (pose estimation failed).
- Character **must face +Z** (standard glTF forward) or pose estimation fails.
- `model_url` must be a public `http(s)` **`.glb` ≤ 400 MB** (or ≤ 100 MB
  data URI). No Draco compression.
- Leverage `input_task_id` instead of `model_url` when rigging something
  just generated — no re-upload, no re-read.
- If the mesh has > 320,000 faces you get `400` — run **Remesh** first with
  `target_polycount ≤ 300000`.
- Optional `height_meters` (default 1.7) improves the rig fit.
- Output includes `basic_animations` (walk + run GLB/FBX, skinned and
  armature-only).

```bash
curl https://api.meshy.ai/openapi/v1/rigging -X POST \
  -H "Authorization: Bearer ${MESHY_API_KEY}" -H 'Content-Type: application/json' \
  -d '{"input_task_id": "<text-to-3d task id>", "height_meters": 1.8}'
```

## Plans, credits, retention

- Free plan: **100 credits/month, no card**. Paid plans raise quotas.
- Example burn: rigging ≈ 5 credits on success, 0 on failure.
- `lowpoly` model retires **Oct 30, 2026** — don't pin it.

## How it plugs into this repo

1. Generate (`text-to-3d` or `image-to-3d` from a cast sheet) → download GLB.
2. `rigging` it (unless the mesh ships rigged).
3. Store under `characters3/<slug>/` with a `mesh.json` sidecar
   (`schema: pogtown.mesh.v1`, see existing packs).
4. Stage `loadAvatar` picks it up by URL; `set_plan.json` declares the mesh
   for the set (`mesh` field). GLB stays embedded — the worker serves it
   with the set's other assets.
5. Re-render textures per season via `retexture` instead of re-modeling.

## Gotchas (learned, not in docs)

- Base path is `/openapi/v1`, not `/v1` (the latter 404s).
- Respect `Retry-After` between polls; don't hammer.
- Download results immediately (3-day expiry).
- Keep keys out of the tree: only `.env` (0600, gitignored); never log,
  never commit.
