# Character meshes (staging)

13 GLB meshes, imported 2026-10-08 from the `stallshark` bucket (same
Cloudflare account) into the canonical `freak-town` bucket under
`character-meshes/`. Server-side copy — the originals are untouched.
All 13 validated: `glTF` magic, version 2, length field matches size.

## Layout

- Bytes (canonical): `r2://freak-town/character-meshes/<filename>` (~242MB total)
- Full pointer list: `manifest.json` (this folder)
- Local cache (gitignored): `data/character-meshes/`
- Fetch: `python3 scripts/fetch_r2_media.py --meshes`

## Why not in git

236MB+ of binaries does not belong in the tree. R2 is the media
authority per ARCHITECTURE.md; this folder holds pointers, not bytes.

## Next step before stage use

These are **staged, not wired in**. Per `backend/services/bodies.py`
("no arbitrary GLB uploads in MVP"), each mesh still needs: download to
local cache, sniff via the `face_profiles` + `_sniff_glb` path (rig?
morphs? visemes? jaw only? static?), then a curated `BODY_CATALOG`
entry for the ones that pass. Static meshes get procedural bob, never
faked mouths.

## Cast (`cast/` — 39 staged character specs, 3 per mesh)

Each mesh has three complete candidate characters in
`cast/<mesh>-<name>.json` plus `cast/cast-index.json`: dramatic core,
3+ interacting contradictions, transgression grammar, relationships
with leverage, voice, comedy operator priors, a sample premise and
joke, callback hooks — and a `theory_map` tagging which theory each
element uses and how (Bergson rigidity/snowball/interference/inversion,
Freud techniques and taboo gates, Attardo script opposition, play-mirth
framing). Staged for the CharacterGraph build-out; mesh links
validated against `manifest.json`.

## License note

Filenames carry author handles (quaternius CC0 is explicit; others are
not). Verify each model's license and riggability before shipping it as
a performer body — community labels don't clear underlying designs
(see DEPENDENCIES.md).
