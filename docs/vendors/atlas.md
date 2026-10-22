# Atlas — vendor brief (imported 2026-09-11)

> DISAMBIGUATION 2026-10-17: TWO different products share the name.
> (A) Atlas.design (below) — mesh generation API. (B) Marble Atlas by
> World Labs (atlas-beta.worldlabs.ai) — world MODEL (prompt → posed
> views → splats → GLB). Owner holds Marble beta access. Section B added
> at the bottom; nothing below was rewritten.

## Mesh pipeline (the part we care about)

Sources: https://docs.atlas.design/ (llms.txt + per-page .md + ?ask= agent
query). Site: https://atlas.design/. Vienna outfit, SEGA/Square Enix
customers, Google Cloud Marketplace. Pricing Pro €50/mo = 5,000 pooled
credits (~250 meshes / 2,500 HQ images); overage €0.01/credit. GLB export
with commercial license. Jam grant = fixed credits for art (reference
images, textures, skies, sound, music).

## Mesh pipeline (the part we care about)

Image→3D (multi-backend: Tripo v3, Meshy v6, Hunyuan Rapid, SAM3D, quad/
triangle/stylized/realistic) → Auto Transform (scale/pivot/semantics) →
Optimize (retopo) → texture/bake high→low → **Rig Humanoid Mesh** (T/A-pose
in, armature + walk/run previews out) → Animate Rigged Model (preset library)
→ Compose Scene → GLB out (FBX/USDZ via DCC). Fallback node retries across
backends (reliability for UGC). Omnipart/Separate-Parts for modular pieces.
Pitfalls they admit: skip Auto-Transform breaks assembly; high-detail needs
bake; rig needs standard pose; texture before optimize.

Verdict for bake-off: Atlas is a legit **6th lane** (managed multi-backend
+ rig + commercial GLB). Add it.

## MCP (alpha, per-workspace on request)

Endpoint: `https://mcp.dev.atlas.design/mcp` (docs; jam invite says
`mcp.prod-market.atlas.design/mcp` — confirm per workspace, they differ).
Auth: workspace key `atk_…` as bearer (env-ref pattern, never persisted).
Verified 2026-09-12: prod-market endpoint is live (keyless probe answers
HTTP 406 = wants MCP handshake, not 404). One observed workspace key was
pasted in chat and must be revoked in the API Keys tab — never persisted
to disk (grep-verified).
Tools: projects CRUD/clone/share · platform-agent ONE-SHOT graph build
(stateless — builds/edits graphs, CANNOT run nodes) · exported APIs
manage · `whoami` verify · MCP-origin labeling.

Limits that matter: agent builds the graph, a browser/webapp run executes
it. No direct "give me the mesh" tool — meshes come from running the graph
then exporting GLB (UI or exported API). Audio nodes exist (speech/music/SFX,
multi-speaker) — walkout lane candidate later, not now.

## What we do with it (credits on hand)

1. Human: create workspace key (API Keys tab, shown once) + enable MCP.
2. Me via MCP: project per bake-off lane input (freak portraits) → graph:
   portrait → Image→3D (fallback node) → Auto Transform → Optimize →
   Rig Humanoid → GLB export.
3. Run in webapp (or exported API), pull GLBs down, run OUR sniffer +
   face-profile battery (ARKit count, visemes, Mixamo compat, three.js load).
4. Score into the bake-off; winner = avatar_generator_primary candidate.

## Under the hood (observed 2026-09-12, badger build)

Platform agent is one-shot and stateless: it searches node types, fetches
specs, adds nodes + connections, then a browser/webapp run executes them.
It cannot run nodes itself — matches the documented limit.

Observed pipeline for "cute badger stand-up comedian":

- Text → Image (High Quality): T-pose character concept, white background.
  Why T-pose: arm separation so the rigger doesn't bind shoulders to hips.
- Image → 3D: Tripo3D v3.1, PBR maps, auto-crop isolate. Output ~1M verts /
  ~2M tris (needs our simplify before web).
- Rig Humanoid Mesh: height param (1.2m for badger), auto-armature + skin
  weights, emits walk/run previews + rig task id.
- Animate Rigged Mesh ×2: preset taxonomy `WalkAndRun :: Walking ::
  Stage Walk` + `DailyActions :: Interacting :: Talk Passionately`.
  Motion is library retarget, not generative — good (deterministic, cheap).

Credit model: max-hold estimate up front (~257cr for the 5-node graph:
image ~100, 3D ~132, rig ~11, anims ~7 each), settles far lower in practice
(badger: image 8cr, 3D 68cr = 76 total). Holds, not spends — still budget
per bake-off lane accordingly.

Intake contract for anything Atlas exports: `scripts/atlas_intake.py`
(GLB path/URL → our sniffer + face-profile battery → size check →
optional upload as a new freak slug). Rigged output should flip badger
from face profile NONE to something with a skeleton at minimum; facial
morphs still unlikely (retarget presets move bones, not faces) — puppet
mode stays the face path until morphs appear.

## Failure log (observed 2026-09-12, badger rig attempt — read before retrying)

1. "Scheduling 2 nodes → Execution failed": the agent first tried to fire
   Rig + Animate together. Fix was wiring: Rig Humanoid Mesh needed an
   explicit Input Mesh edge to the generated mesh before it would run.
   If a run fails instantly, check edges before credits.
2. Meshy rig caps at ~300k faces. Tripo v3 output is ~2M tris, so the
   Meshy-backed Rig Humanoid Mesh node can never take raw Tripo output.
   The agent's pivot: delete the Meshy nodes, use **Rig Tripo Mesh**
   (native high-density support, no decimation) + **Animate Tripo Mesh**
   (multi-clip: v1+v2 walk, v1 biped swagger, v1 biped greet 01).
   Rule for bake-off lanes: Tripo meshes stay on the Tripo rig track;
   only decimated (<300k) meshes may go near Meshy rigging.
3. No detail was lost in the pivot — no decimation step, full 1M-vert
   mesh into the Tripo rigger. Our web simplify still happens at intake.

## Rig output verdict (observed 2026-09-12, stallshark animation_1/2.glb)

Tripo rig emits a 41-bone Mixamo-style armature (Root/Pelvis/Spine/Head,
L_/R_ limbs with Twist01/02 segments, ToeBase), skinned, with named
actions (`preset:walk_Armature`, `preset:biped:swagger_Armature`).
Raw: ~2M tris / 79MB per clip. Factory decimate 0.1 → ~200k tris / 11MB
with all 41 bones + skin intact; intake battery passes; watch/AR/record
all 200. No facial morphs (as predicted — puppet mode stays the face).
animation_3.glb had not landed in the bucket at intake time.

---

## (B) Marble Atlas — World Labs world model (refreshed 2026-10-17)

Sources (fetched today): docs.worldlabs.ai/llms.txt index + api quickstart,
models, pricing, worlds/export reference, chisel-basics, mesh export.
Old beta (`atlas-beta.worldlabs.ai/api/v2`, `atlasChisel`/`atlasGenerate`/
`splats2Mesh` names) is SUPERSEDED — current API below. Key
`WLT_API_KEY` (header `WLT-Api-Key`, NOT on box — owner holds beta access).

Base: `https://api.worldlabs.ai`. Auth header: `WLT-Api-Key: YOUR_API_KEY`.
Flow: `POST /marble/v1/worlds:generate` → returns `operation_id` →
poll `GET /marble/v1/operations/{id}` until `done:true` (~5 min) →
`GET /marble/v1/worlds/{id}` for asset URLs → view at
`marble.worldlabs.ai/world/{id}` → `POST /marble/v1/worlds/{id}:export`
for GLB.

Generate inputs: `text` / `image` (uri or media_asset) / `multi-image`
(azimuth per view) / `video` / pano. For Cauldron we use TEXT (profile
prompt is the world prompt) — optionally multi-image later from the 10
posed views. Models: `marble-1.1` (rooms), `marble-1.1-plus` (biggest
rooms, variable cost), `marble-1.0`, `marble-1.0-draft` (cheap layout
proof). Chisel today = web-app 3D blocking (walls/pano-camera/GLB-FBX
upload → Generate button); no public Chisel POST — blockout lives in
our `cauldron.json` + profile prompt, submitted as text.

Export: `{"asset_type":"mesh","format":"glb"}` → async HQ mesh op
(up to ~1h, Pro plan, ~600k-tri textured + ~1M-tri vertex-colored,
typically 100–200MB — WE decimate to ≤30MB before lock). Collider mesh
is physics-only, not visual. PLY splat export is free. Cached exports
cost nothing twice (existing op returned, no charge).

COST (ask-first, $0 rule — owner approves every live call):
1,250 credits = $1.00. Text→world on marble-1.1 = 80 + 1,500 = 1,580
(~$1.26). Draft text→world = 80 + 150 = 230 (~$0.18). HQ mesh export =
3,500 (~$2.80). Cauldron lock budget: draft proof $0.18 + real
$1.26 + mesh $2.80 ≈ **$4.24 max**. Credits are Platform-only
(platform.worldlabs.ai/billing) — Marble app credits do NOT work.
402 = out of credits. Polling + uploads are free.

COMPATIBILITY (verified in code, not claimed):
- Marble GLB (club, static) + Mutuals/FUNNIER VRM (performers) compose
  in ONE three.js scene. VRM 1.0 is glTF under the hood; our importmap
  already loads it (@pixiv/three-vrm 3.3.0).
- Mutuals avatars are `.vrm` models + `.vrma` clips baked onto the
  skeleton (`extras.mutualsHarness` table) — NOT plain GLB. FoxGlove uses
  a cooked player profile. Do not convert VRM→GLB and expect motion to
  survive; keep performers VRM, rooms GLB.
- Align frames: Marble camera math page before compositing (Y-up vs
  camera conventions); floor-position cast against predicted (approx)
  metric scale.
- Non-humanoids stay clips/props (retargeter can't wear them).

CLUB PLAN: atlasChisel blockout (stage box + seat rows as depth) →
generate 8–12 posed views → splat → GLB → our stage. Comedians (VRM)
and hecklers (pips/faces) composite live. Static crowd as inpainted
objects via atlasMasked; live crowd stays ours.
