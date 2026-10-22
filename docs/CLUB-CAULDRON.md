# THE CAULDRON — venue spec v1 (SPEC ONLY, 2026-10-17)

First club. A Marble-splat basement comedy room our VRM cast performs in
and our audience haunts. This doc defines the canonical things a
performer and an audience member ARE inside the splat. Nothing below runs
yet; it becomes build tasks once the Atlas key lands.

## Layers (one three.js scene, back to front)

1. ROOM — Marble GLB (static): floor, brick walls, bar, seats, curtains.
   Baked lighting STABLE (no disco in the splat — light show runs live).
2. LIGHT RIG — three.js lights (ours, live): 1 warm directional w/ shadows
   + ambient matched to generated views + 1 follow-spot + 2 color washes.
   Hits room AND bodies together (sells the composite).
3. CAST — VRM performers (own parse each, animated per-frame).
4. CROWD — pips (far), faces (WebRTC near), impostor bodies (reserved).
5. CAMERAS — WIDE/MEDIUM/CLOSE/SIDE presets + audience POV.

## Performer (canonical)

- Body: `.vrm` (VRM 1.0), own `GLTFLoader` parse, own humanoid/expression/
  spring managers. Never shared, never cloned (three-vrm v3 can't rebind).
- Anchor: feet-on-floor at a stage mark (see stage plot). Scale: meters,
  1 unit = 1 m. Facing: +Z toward room (normalize authored facing on load).
- Drivers (apply order: bones → lookAt → expression → springs):
  - voice → visemes (v1 5-shape envelope; phonemes when Rhubarb lands)
  - beats → expressions/gestures/holds (acting timeline, already served)
  - idle → sway + blink timer (already running)
- Voice: set audio or TTS, 24 kHz. Casts no shadow map of its own; receives
  room shadows (directional light, floor receives).
- Slots: 1 headliner center-stage + 2 wing marks (guest/heckler VRM).
- Fallback: no VRM → portrait + captions (current rooms). Never black.

## Audience member (canonical tiers)

- PIP (default): glow dot + nickname. Zero camera, zero audio. Counts for
  energy, votes, KILLED distinct-tapper rule.
- FACE (opt-in 1, TRACK): boolean smiles leave the device. Feeds heat-vs-
  observed + finale graph. Never shows pixels anywhere.
- ON-STAGE (opt-in 2, APPEAR): WebRTC face to the monitor + front-row
  impostor body (billboard, not a parse). ≤6 per room (mesh ceiling).
- VOICE (opt-in 3, MIC): laugh bursts as booleans; personal laugh sample
  only if recorded + shared (monitor mix).
- SEAT: every member holds a seat id (table/row) for directed shots
  ("table 3 is dying") and heckle routing. Seats are stable per night.

## Stage plot (meters, Y-up, room origin at stage center-front)

- Stage deck: 4w × 3d, front edge at z=0, back wall z=-3. Height 0.6.
- Mic mark: (0, 0.6, -1.2). Headliner home: (0, 0.6, -1.2) facing +Z.
- Wing L/R: (±1.5, 0.6, -2.2). Follow-spot: (0, 4.5, +2.5) → mic mark.
- Front row: z=+1.5..+3 (faces/impostors). Pips: z>+3 (pitch dark).
- House cameras: WIDE (0,2.2,+7.5) · MEDIUM (0,1.7,+4.2) · CLOSE (0,1.6,+2.4)
  · SIDE (+3.5,1.8,+2.0). FOVs 46/34/28/40 (match CameraDirector numbers).

## Atlas pipeline (runs once per venue, offline)

1. `atlasChisel`: depth blockout of the plot above (deck box, seat rows,
   bar block, curtain plane) + prompt (brick basement, velvet, spotlight,
   haze). 2. `atlasGenerate`: 8–12 posed views covering stage + room.
3. Splat → `splats2Mesh` → `cauldron.glb` (+vertex colors). 4. Import:
   verify floor at y=0, scale meters, bake STABLE warm light. 5. Lock:
   hash-pin the GLB; rooms reference it by hash, never latest.

## Contracts (wire, all JSON)

- `GET /api/venue/cauldron` → {glb_hash, plot, light_rig, camera_set}.
- Performer join: `{vrm_url, mark}` → server checks mark free, returns
  `{slot, parse_id}`. One parse per performer enforced server-side.
- Audience join: `{tier, seat?}` → `{seat_id}`. Tier upgrades re-announced
  on presence (face/pip/voice flags already served).
- Reaction stream unchanged (/api/react + feed). Verdict unchanged.
- Camera cuts emit `camera.cut` events (steal from CameraDirector).

## Budgets (hard)

- ≤3 VRM parses/room (headliner + 2 wings). Everyone else pips/impostors.
- Room GLB ≤ 30MB (decimate rural geometry; seats are boxes).
- 60fps on a 3-year-old phone or the room degrades: pips first, then
  shadows off, then washes off. Never drop the performer.

## Out of scope (explicitly)

- Dynamic club lighting baked into splats (Disco-GS says no).
- VRM→GLB conversion for performers (motion doesn't survive).
- Non-humanoid headline acts (clips/props lane, unchanged).
- Second venue before Cauldron kills (verdict-gated expansion).
