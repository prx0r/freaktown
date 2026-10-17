# THE CAULDRON — venue profile v1 (CANONICAL, 2026-10-17)

The single source of truth for what the room IS. Atlas jobs, light rigs,
camera framings, and acceptance gates all derive from this page. Change
the room here first; everything downstream follows.

## Identity

- Name: THE CAULDRON. Basement comedy room, 40 seats, always nearly full.
- Hour: 11:40pm forever. The show started late and the night is warm.
- Rule of the room: DINGY. Bare mic on a stained stage. Brick, sweat,
  one spotlight. Nothing chrome, nothing daylight, nothing corporate,
  nothing decorated. It smells of beer and fog. If it looks dressed, cut it.

## Shell dimensions (meters, Y-up, origin at stage front-center)

- Room: 12w (x −6..+6) × 9d (z −3.5..+5.5) × 3.4h. Floor y=0.
- Stage deck: 4.5w × 3d, front edge z=0, back z=−3, top y=0.6. STAINED
  wood planks running stage-left↔right, ring marks, tape residue, one
  worn pale circle center where a thousand feet stood. Mop it never.
- Center stage: ONE mic stand (brass-weighted base, pole, SM58 ball,
  cable drooping to deck). No stool unless the act brings one. NOTHING
  else on the deck. The bare mic IS the room.
- Back wall (z=−3.5): damp brick, paint peeling (#141114 over older
  green), one chalk cauldron outline, 1.2m wide, centered x=0, y=1.9 —
  chalk, not gold. Redrawable, already smudged.
- Side walls: brick #1d1512, water stain high right, 2 peeling handbills
  (illegible pulp, taped, curling). No frames. No gallery.
- Curtains: one black traveler each side (x=±2.4), dust-dulled, half-open
  and crooked. No valance, no velvet shine.
- Ceiling y=3.4: matte black, 2 duct runs, 1 dead bulb in a wire cage
  (x=+2.5, z=+2, OFF). NO Edison strings. The crowd sits in the dark —
  faces catch the spill, nothing else.
- Floor: concrete, painted black, worn through to gray at the aisles.
  Sticky near the bar. Honest.
- Bar: back-right suggestion only (x +3.5..+5.5, z +3.5..+5.5): counter
  edge + back-shelf bottle blur + 1 out-of-focus silhouette. No brass
  rail, no detail. It exists so thirst exists.
- Tables: 6 scarred cocktail tables (r=0.4, h=0.75), black, NO candles,
  NO glasses. Ashtray on two (glass blobs, unlit).
- Seats: 40 total — folding chairs (black metal, rows z=+1.5/+2.5, EMPTY,
  not quite aligned) + 16 stools (back + bar). All EMPTY except the
  blurred silhouette. People never bake.

## Light grade (baked, STABLE — the light show runs live on top)

- House: near-dark. 2700K cans at 0.15 — enough to find your seat,
  not enough to read. Crowd is shadow with spill on faces.
- Follow-spot cone: visible haze cone from booth (0, 3.2, +5.2) to mic
  mark, 4000K core, hard-edged. The cone is geometry+haze, not a live
  light — the live spot aligns to it nightly. Everything else drowns.
- Practical accents: bar shelf amber blur, EXIT green over back-left door
  (x=−5.5, z=+5.2, small, buzzing). That's all the color in the world.
- BANNED from bake: disco color, moving gobos, daylight windows (there
  are NO windows — basement), strobes, LED walls, candles, Edison strings,
  fairy anything. Marble loves dressing rooms; forbid all of it, every prompt.

## Acoustic character (for beds + TTS direction)

- Small-room verb: RT60 ≈ 0.7s, warm, slight slap off the back wall.
- Crowd bed sits −14dB under voice. Brick eats highs; voices stay chesty.
- Walkout sting: swampy blues riff, 8s, tube amp, room mic (not direct).

## Cast marks (performers stand HERE, feet snapped)

- Mic mark: (0, 0.6, −1.2), facing +Z. Brass-weighted mic stand,
  SM58-ish ball mic, cable drooping to deck.
- Wing L/R: (±1.5, 0.6, −2.2). Stool (wood, tall) at wing R only.
- House cameras: WIDE (0,2.2,+7.0,46°) · MEDIUM (0,1.7,+4.2,34°) ·
  CLOSE (0,1.6,+2.4,28°) · SIDE (+3.5,1.8,+2.0,40°).

## Atlas job spec (exact)

- Step 1 chisel: depth blockout of §Shell (boxes only: deck, 6 table
  cylinders, 40 seat boxes, bar L, curtain planes, back wall) + prompt:
  "dingy empty basement comedy club at night, damp peeling near-black
  brick, stained wood stage with ONE brass mic stand center and NOTHING
  else, black crooked curtains, scarred tables, folding chairs, concrete
  floor worn gray, green EXIT sign, chalk cauldron outline on back wall,
  NO people, NO windows, NO daylight, NO candles, NO string lights,
  near-dark 2700K house, hard spotlight haze cone to the mic, beer and
  fog, mop it never".
- Step 2 generate: 10 posed views — 3 stage-front (wide/medium/close),
  2 side, 2 rear-booth, 2 bar, 1 curtain detail. 1280×720, reuse
  promptUsed, enhancePrompt false after view 1.
- Step 3 masked edits (only if needed): remove any humans/windows Marble
  invents; smudge any legible poster text.
- Step 4 splats2Mesh → cauldron.glb + vertex colors. Budget: ≤30MB.
- Lock: floor y=0 check, meter scale check, sha256 pin. Reference by
  hash from `/api/venue/cauldron`.

## Acceptance gates (all must pass before lock)

1. Empty-room test: zero humanoid shapes except the blurred silhouette.
2. Window test: no daylight, no glass but ashtrays.
3. Floor test: deck top y=0.6±0.05, room floor y=0±0.05, meter scale.
4. Sigil test: chalk cauldron outline on back wall, smudged.
5. Bare test: deck holds mic stand ONLY. No stools, no tables on stage,
   no candles, no strings, no frames. Count the props: exactly the
   registry (mic + curtains + stool-wing-R if booked).
6. Size test: GLB ≤30MB. 7. Night test: 3/3 reviewers say "dingy".
