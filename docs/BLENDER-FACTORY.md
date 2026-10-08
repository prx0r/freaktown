# Blender factory v1 — inspect, transform, prove (headless, CPU)

`scripts/blender_factory.py` runs INSIDE Blender 4.2 (`~/blender`), one
process per call, JSON report on stdout. No node runtime, nothing to
install. Pattern mirrors `@three-ws/blender-mcp` (see three.ws clone);
direct bpy is simpler for our single-box use.

```bash
~/blender/blender -b --python scripts/blender_factory.py -- \
  --in /tmp/x.glb --out /tmp/factory/x [--decimate 0.5] [--views 4] [--export y.glb]
```

Report: meshes, tris before/after, verts, armatures + bone names,
actions, materials, metres-tall, preview PNGs, export path.
Static meshes never fail inspection — they report `bones: []`.

Requires system `libegl1` for Workbench renders (installed 2026-09-12;
without it, import + report still work, previews don't).

## Reuse map (do NOT rebuild)

| Job | Use | Lives |
|---|---|---|
| Headless inspect/convert/optimize/render/export | this script (+ three-ws `blender-mcp` package if an MCP client ever needs it) | `scripts/blender_factory.py`, `~/three.ws/packages/blender-mcp` |
| Control rig + bake on Mixamo skeleton | Mixamo Rig add-on v1.2.2 (Blender 4.2 LTS ✓) | extensions.blender.org |
| Mixamo clips → canonical Rigify | mixaify.py (single script, Blender 5 in title — verify on 4.2) or YeLanQ mixamo_retarget | GitHub |
| Mixamo → VRM at runtime (browser) | `vrm-mixamo-retarget` npm (bone map + height scale) | npm |
| Any-skeleton → canonical bones | `glb-canonicalize.js` + `animation-retarget.js` (universal clips, no allowlist) | `~/three.ws/src/` |
| Mixamo↔Rigify bone table | frnsys gist `mixamo.json` | GitHub gist |
| Video → Mixamo-rig animation | GVHMR estimator track (topic: mixamo) — evaluate for PERFORM upgrades | GitHub topics |
| Face solver | NOT Kalidokit for faces — direct ARKit→VRM map (already shipped in RECORD) | `app.py` RECORD_TEMPLATE |

## Proven 2026-09-12

`/tmp/badger-30k.glb`: 1 mesh, 59,470 tris, 39,030 verts, 0 armatures,
Tripo PBR material, 0.92m tall, 4 clay previews rendered headless on CPU.
Next: same script verifies the Atlas rigged export (expect bones > 0),
then `scripts/atlas_intake.py` takes it live.
