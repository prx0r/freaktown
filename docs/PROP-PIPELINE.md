# PROP PIPELINE — spec (2026-10-16, no local Blender: spec only)

Prompt adjectives → one procedural 3D object → every style. Blender is
the scene graph; style is a render setting. Nothing here installs or runs
until a GPU box exists. This doc is the build contract.

## Job manifest (`prop_job.v1`)

```json
{
  "version": "prop_job.v1",
  "prompt": "a triumphant peanut, slight glow",
  "adjectives": ["triumphant", "glowing"],
  "primitives": [{"op": "uv_sphere", "scale": [1, 1.4, 1], "material": "peanut_shell"}],
  "materials": {"peanut_shell": {"base": "#c89b6a", "roughness": 0.8}},
  "style": "anime",
  "cameras": ["hero_34"],
  "out": ["still_1080.png", "prop.glb"]
}
```

- `primitives`: closed op vocabulary (sphere/box/cylinder/torus/cone/plane
  + transform + named material). The prompt compiler (LLM) may ONLY emit
  these ops — never raw `bpy`. This is the sandbox boundary.
- `style`: preset name resolved server-side to a renderer + shader stack
  (see below). New styles = new preset files, never new code paths.

## Pipeline stages

```
prompt → compile (LLM → manifest, op-vocab validated, reject + retry on
         unknown ops) → build (headless blender --background, manifest in)
       → verify (freestyle/edge sanity, poly budget, 3-view contact sheet)
       → style render (preset stack) → export (PNG still + GLB)
       → inventory (night inventory ID, memorial-eligible)
```

- Runner shape: `blender-cli` pattern — single-file headless runner,
  manifest in, one clean JSON result on stdout, noisy Blender logs
  swallowed. No MCP daemon, no HTTP service, no API key.
- Batch: kiln-style YAML manifest of N jobs → overnight queue. Pocket
  objects for a season in one run.
- Verify gate: contact sheet (front/34/top) must show exactly one
  connected object, non-zero pixels, under poly budget — else retry with
  simplified primitives (sphere + material, the dignified fallback).

## Style presets (author once, reuse forever)

| Preset | Renderer | Stack |
|--------|----------|-------|
| `matcap` (preview) | Workbench | MATCAP + cavity, existing `render_set.py` path |
| `anime` | EEVEE | toon BSDF + Freestyle lines + limited palette + halftone compositor |
| `noir` | EEVEE | high-contrast B&W, single hard key, fog |
| `clay` | Workbench/EEVEE | matte subsurface-ish, fingerprint normal noise |
| `hero` | Cycles | one beauty still per night max (champion's prop) |

## Integration points (already exist)

- In: pocket-object slot winners (E3 prop engine), memorial intake, trophy
  exports, Atlas `atlasMasked` set dressing (still PNG as context view).
- Out: `performances/<id>/prop_<n>.{png,glb}` (R2 layout), night
  inventory IDs for callback engine, memorial gallery.
- Budget: previews free (Workbench, seconds); hero Cycles stills capped
  at 1/night. No per-round GPU spend, ever.

## What the GPU box needs (when it exists)

Blender 4.4+, headless, the single-file runner, preset `.blend` library,
poly budgets per preset. ~300MB install — explicitly NOT on this box
(disk). First runbook: install → dry-run manifest → contact sheet →
ship.
