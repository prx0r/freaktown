# Atlas — vendor brief (imported 2026-09-11)

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
