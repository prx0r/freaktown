# Set assets — sources and licences

Every set renders **procedurally with zero downloads** (`packages/stage-runtime/src/sets/builders`).
No binary set assets are committed. Third-party GLBs are optional decor loaded at runtime
from the publisher's CDN (`environment.glb` in `sets/definitions.ts`); a failed load keeps
the procedural set. Unverified framing loads only with `/stage/:ep?setglb=1`.

| Set | Asset | Source | Author | Licence | Use |
|---|---|---|---|---|---|
| news-studio | Studio Floor and Production Gallery (63,902 tris, 2.53 MB GLB) | https://3dassets.dev/assets/tv-studio-and-broadcast-gallery-studio-f-0d3b5716-starter-scene · GLB https://cdn.3dassets.dev/assets/35527/v1/model.glb | 3D Assets (@3dassets) — contributor reports AI-assisted | CC0 1.0 (no attribution required) | optional decor, runtime CDN, **framing unverified** (CDN unreachable from the build sandbox) |
| podcast | Studio Desk Setup (29,218 tris, 1.15 MB GLB) | https://3dassets.dev/assets/computers-and-desk-gadgets-studio-desk-s-bc42c4fb-starter-scene · GLB https://cdn.3dassets.dev/assets/38878/v1/model.glb | 3D Assets (@3dassets) — contributor reports AI-assisted | CC0 1.0 | optional decor (desks/shelves behind the table), runtime CDN, **framing unverified** |
| poker-table | — (procedural oval 3.0 × 1.4 m, top 0.78–0.8 m, modelled on the dimensions of polyfork's Tournament Poker Table) | https://polyfork.dev/asset/tournament-poker-table-a75b66 | Polyfork | **paid** (Pro/Lifetime subscription; commercial licence after purchase) — **not used**, no bytes copied | dimensions only |
| poker-table | mehrasaur Poker Pack (OBJ) | https://opengameart.org/content/poker-pack | mehrasaur | CC0 (per OpenGameArt listing) | **not used** — cards/chips are procedural canvas textures |
| all | poker-ts (hand state machine, npm) | https://github.com/claudijo/poker-ts | claudijo (port of JankoDedic/poker) | MIT | dependency of `@freaktown/stage-runtime` |

PolyClem's studio starter pack was not used (licence not clearly permissive for this use).
Sketchfab 1M+ tri studios were avoided.

## Adding an asset

1. Check the licence on the asset page (CC0 / CC-BY / MIT-style; record attribution if required).
2. Prefer the publisher's immutable CDN URL with CORS; commit bytes only when < 5 MB after
   `gltf-transform optimize` (meshopt/draco), under `apps/live/public/sets-assets/`.
3. Add a row here and the `environment.glb` block (url, licence, source, transform, `verified`).
