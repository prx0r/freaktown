# PogMotion — Canonical Puppet Animation and Visual QA (Pogtown Puppet Lab)

Saved 2026-10-08. Directing miniature theatrical performers, not
animating 3D characters realistically. Stop-motion charm is the target:
deliberate, slightly imperfect, expressive stillness.

## Canonical aesthetic

Tactile materials, economical poses, stepped motion, anticipation,
memorable holds, clear silhouettes, nonhuman movement with weight.
Principles (law): strong poses beat complex movement; stillness is
performance (freeze on the punchline while the audience processes);
movement has personality (never interchangeable); bodies feel physical
(settling, inertia, anticipation — no constant wobble); animate
meaning, not every word; small imperfections are intentional; faces
carry disproportionate value. An inanimate object is a valid performer:
a toaster needs no arms. Every Pog owns a signature way of holding
still — resting pose is identity. Grammar: signature pose →
anticipation → expressive action → delayed reaction → settle → hold.
Five to eight signature gestures per character, never hundreds. The
performer must sometimes do absolutely nothing.

## Temporal imperfection (stepped sampler)

Pose changes sampled below display rate: body acting 12 unique
poses/s, big gestures 8–12/s, mouth 12–24/s, camera smooth, environment
never quantized. Quantize puppet channels only. Stepped motion without
good poses is just low frame rate: expressive poses + controlled
spacing + holds + stylized timing.

## Four movement families

Articulated (giraffe/dog/bird/monster: head/neck/torso/limbs; neck
leads, head reacts late). Hovering (mosquito/ghost: hover offset,
pitch/yaw, micro-adjustments speaking, unnatural stillness for power,
sudden repositioning). Rigid-body (toaster/cone: pivot, rock, squat,
wobble, lean — no arms required). Squash-and-stretch (snail/blob:
root motion, compression, tilt, telescoping). Shared intent
vocabulary: idle, listen, speak, emphasize, confess, boast, panic,
react, pause, laugh, exit — family adapters realize each intent
differently (a toaster's look_left is whole-body rotation).

## Virtual puppet controls + graceful fallback

GLBs won't share skeletons; some have no bones. Infer control points
from the model, correct in a lightweight calibration UI, never let
auto-inference be silently authoritative. Fallback is whole-body
acting: root rotation/translation, off-center pivots, lean,
squash/stretch, attachments, interchangeable mouths, decals, props.
Pipeline: load → inspect (meshes/bones/anims/morphs/bounds/front/
ground) → suggest family → virtual control hierarchy → calibration
sheet (front/side/three-quarter, rest, leans, mouth closed/open,
speaking, emotional extreme, silhouette, stage position) → creator
correction → versioned PuppetRigProfile.

## Mouths (replacement first)

Three adapters, preference order: replacement mouth (swap prebuilt
mouth mesh/texture per timed phoneme — stylized, reliable, cheap;
per-character mapping, e.g. sideways mouth, proboscis, toaster slots),
morph mouth (existing jaw/blendshapes), simple flap (envelope-driven
jaw). Rhubarb Lip Sync shapes the timing vocabulary (6+idle shapes,
JSON cues). Mouth never moves alone: stress syllables → small head/
torso emphasis; sentences → gaze changes; punchlines → posture shifts;
long pauses → eye move or full freeze. Sparse and controlled — no
constant synchronized head-bobbing.

## PogMotion engine (layered, not one clip)

Performance semantics (confess/brag/pause/react/panic/joke/callback)
→ pose engine (keys, anticipation, overshoot, holds) → character style
(temperament, rhythm, habitual gestures) → speech controller (visemes,
breath, emphasis) → physicality (weight, pivot, settling, balance) →
rig capability resolver (articulated/floating/rigid/squash) → stepped
sampler → renderer. Motion style profile per character
(`pog.motion-style.v1`: family, body/mouth cadence, energy/confidence/
nervousness/theatricality, primary control, gesture frequency,
preferred pose, reaction delay, signature action, settle/overshoot/
breath). AnimationMixer-style blending with per-channel ownership —
no fighting over bones.

## QA (evidence, not claims)

Reproducible fixtures (asset hash, controller version, world pack).
A: GLB preflight (schema, bounds, orientation, materials, skeleton,
morphs, capabilities, anchors, face visibility — no skeleton resolves
to a simpler family, never fails). B: mouth reality (commands issued?
mesh visibly changing in rendered mouth region? aligned to audio?
<80ms median target, <5% silence motion; stillness during silence is
correct). C: timing quality (pose-cadence logs excluding face/camera;
per-intent visual evidence table; plausibility: no slide/penetration/
drift/pops; repetitiveness: repeated cycles, pose diversity, emphasis
aligned to meaning — restraint is legal, compare against the
character's style, not a universal activity target). D: spatial
(staged for Marble/Spark: grounding, scale, occlusion, halos,
lighting integration via one stage look preset, framing, perf,
asset-hash stability). E: the agent watches (contact sheet, mouth
close-ups, clips, timeline diagnostics; deterministic Evaluator A plus
multimodal Evaluator B citing timestamps and evidence; feedback as
parameter changes — gesture_frequency, head_amplitude, pose_hold,
mouth_scale, settle_strength, reaction_delay, look_target,
camera_closeup — never unexplained scores).
Golden library: articulated / hovering / rigid / expressive-timing
benchmarks, fixed 30s scripts (entrance, dialogue, silence, emphasis,
fast speech, deadpan, interruption, exit), acceptance matrix (100%
structural, timeline integrity, rendered-frame mouth proof, sync
target, grounding, framing, playable export, human-approved goldens).
Tuning loop with bounded changes and human-approved reference gallery;
regression renders four goldens on every motion-affecting change.
Never claim quality from passing tests alone — ship video evidence.

## Tooling

AnimationMixer-style playback, Spark (later), Rhubarb or equivalent,
glTF Validator, Playwright + FFmpeg + telemetry base harness, OpenCV
where measurement beats opinion, multimodal critique as second-stage
assessor only. Puppet Lab (`/studio/puppet-lab`): live renderer,
motion preview with cadence/energy/hold controls, synchronized
audio/viseme/pose/gesture/camera plots, before/after comparison.
Proposed code layout: `packages/pogmotion/` (core clock/sampler/
compiler/style-resolver, family adapters, facial adapters, rig
inspect/infer/calibrate/validate), `apps/puppet-lab/`, visual tests
with fixtures and reports.
