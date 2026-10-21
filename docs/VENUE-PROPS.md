# VENUE PROPS — registry (canonical)

Every prop a venue lists must have a `### <id>` section here or validation
fails. `source: procedural` = built from three.js primitives at load (no
download, always works). `pack` = needs the asset pack named.

## base pack (always available)

### mic-stand
Pole (h=1.6, brass-weighted round base r=0.16), boom arm optional, SM58
ball (r=0.05, dark steel) + drooping cable (quadratic curve to deck).
source: procedural. anchor: deck point. THE prop — every venue has one.

### stool-tall
Wood, 4 legs, round seat h=0.75. source: procedural. Wing-R by default,
bookable elsewhere.

### curtain-traveler
Black dust-dulled drape plane with sine folds, crooked hang (tilt 3°).
source: procedural. Stage sides. Never velvet shine (dingy rule).

### table-cocktail
Black cylinder top r=0.4 + pole + disc base, h=0.75. source: procedural.

### chair-folding
Black metal frame + seat plane. source: procedural. Rows never aligned
(jitter ±4° yaw at placement).

### stool-bar
Dark wood, round seat h=0.8. source: procedural. Back rows + bar.

### bar-counter
Wood box counter + back-shelf blur planes (amber/green emissive dots).
source: procedural. Suggestion of a bar, not a bar.

### ashtray
Glass blob (squashed sphere, transmission 0.6), unlit. source: procedural.
Max 2 per venue (dingy, not decor).

### exit-sign
Green emissive box + white EXIT (canvas texture), faint buzz flicker
(opacity noise 0.9-1.0). source: procedural. Back-left door always.

### easel
Tripod legs + tilted board (1.2×0.9 white plane, faint grid). The
freaktionary canvas anchors here. source: procedural.

### bulb-cage
Dead bulb in wire cage (torus rings + sphere, unlit). source: procedural.
One per venue max. The room's honesty certificate.

### chalk-sigil
Cauldron outline, chalk-white line loops on back wall, pre-smudged
(jitter vertices 2cm). source: procedural (line segments, not texture).

## band pack (addon, M+ venues)

### drum-kit
Kick + snare + 2 toms + hats + crash (cylinders + discs), matte black
with one red shell. source: procedural. Stage-left rear mark.

### guitar-stand
A-frame stand + leaning guitar silhouette (box body + stick neck — no
detail at distance). source: procedural.

### keys-rig
Folding X stand + slab (box, 61 suggestion keys via texture stripes).
source: procedural. No playable keys (v1).

## judging pack (addon, M+ venues)

### judging-desk
Long black table (2.4×0.6×0.75) facing stage. source: procedural.

### judging-chair
High-back chair ×3 behind desk. source: procedural.

### buzzer
Red dome button per judge (cylinder + emissive red top). Pressable look
only in v1 (lights on tap = client-side CSS, no state). source: procedural.
