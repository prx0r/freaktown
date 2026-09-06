# Killella Motion System — Architecture

> Save as anime.dm — canonical reference for the motion/animation system.

## Core Principle

**Standardize intent, not anatomy.**

Every character exposes capabilities. Every creator/agent writes a reusable Performance Engine against Killella's semantic movement language. Killella compiles that into whatever skeleton/body the character actually has.

---

## 1. Semantic Movement Language

Never ask agents to manipulate bone rotations. Never ask them to choose animation file names. Make them control concepts.

```yaml
performance:
  style:
    energy: 0.35
    stillness: 0.78
    gesture_density: 0.22
    gesture_amplitude: 0.65
    eye_contact: 0.85
    pacing: 0.15
    punchline_hold_ms: 1100

  signature_moves:
    - name: Nolan Stare
      action: reaction.dead_stare
      trigger: after_big_punchline

    - name: Paw of Authority
      action: gesture.emphasize
      intensity: 0.8

  rules:
    - during: setup
      prefer: [gaze.audience, gesture.beat]
    - during: punchline
      prefer: [movement.freeze]
    - after: punchline
      hold_ms: 900
    - on: audience_big_laugh
      do: reaction.enjoy_laugh
```

---

## 2. Body Capabilities

Bodies expose capabilities, not skeletons.

### Humanoid v1
```json
{
  "bodyClass": "humanoid-v1",
  "capabilities": [
    "locomotion.walk", "locomotion.pace",
    "gaze",
    "gesture.beat", "gesture.point", "gesture.shrug",
    "reaction.dead_stare",
    "pose",
    "face.expression"
  ]
}
```

### Quadruped v1
```json
{
  "bodyClass": "quadruped-v1",
  "capabilities": [
    "locomotion.walk", "locomotion.pace",
    "gaze",
    "gesture.emphasize",
    "reaction.dead_stare", "reaction.confused",
    "pose.sit",
    "tail"
  ]
}
```

### Rigid Object v1
```json
{
  "bodyClass": "rigid-object-v1",
  "capabilities": [
    "gaze",
    "gesture.emphasize",
    "reaction.dead_stare",
    "pose",
    "prop.actuate"
  ]
}
```

### Semantic Fallbacks

```
                   HUMANOID       DOG             TOASTER
gesture.shrug      shoulder shrug head tilt       body tilt
gesture.point      point finger   raise paw       rotate toward target
dead_stare         face + eyes    head + eyes     freeze completely
nervous            fidget hands   paw shuffle     vibration
celebrate          arms up        jump/tail       eject toast
```

---

## 3. Performance Engine

Not attached to one joke. Persistent, versioned, reusable.

```text
@tom/deadpan-dog-v7
@alice/manic-goblin-v12
@bob/awkward-corporate-v4
```

Contains:
- style profile
- timing policy
- motion selection policy
- signature moves
- reaction policy
- gaze policy
- silence policy
- animation preferences
- body fallbacks
- version history

---

## 4. Motion Bank Pipeline

```
CMU BVH + Mixamo + 100STYLE + creator-owned + Killella original
        ↓
    NORMALIZER
        ↓
    killella-humanoid-v1
        ↓
    semantic tagging
        ↓
    motion embeddings
        ↓
    R2 motion catalog
```

### Motion Asset Metadata
```json
{
  "id": "motion_392",
  "semantic": ["gesture.beat", "gesture.emphasize"],
  "text": "small irritated hand emphasis",
  "style": ["annoyed", "restrained", "deadpan"],
  "bodyClass": "humanoid-v1",
  "loop": false,
  "rootMotion": false,
  "additive": true,
  "boneMask": "upper_body",
  "energy": 0.32,
  "amplitude": 0.4,
  "durationMs": 710,
  "source": "cmu",
  "license": "...",
  "attribution": "..."
}
```

---

## 5. Additive Animation Layers

```
BASE        idle / walk / sit
+ UPPER     gesture / shrug / point
+ HEAD      gaze / tilt / nod
+ FACE      emotion / blink / viseme
+ PROCEDURAL breathing / sway / micro-fidget
```

### First-Class Comedy Parameters
- STILLNESS
- GESTURE DENSITY
- GESTURE SIZE
- EYE CONTACT
- MOVEMENT DURING SETUP
- PUNCHLINE FREEZE
- POST-LAUGH REACTION

---

## 6. MCP Interface

```text
character.get_capabilities
character.get_motion_catalog
performance.create_engine
performance.compile
performance.preview
performance.explain
performance.validate
```

---

## 7. Creator Interfaces

### Dressing Room (normal users)
Presets: DEADPAN, NERVOUS, CONFIDENT, CHAOTIC, AWKWARD, AGGRESSIVE, LOW ENERGY, CUSTOM
Natural language description → REHEARSE → watch → iterate.

### Advanced Timeline (power users)
```
00:00 ───────────────────────────────── 00:59
VOICE   ████████████████████████████████
SCRIPT  setup────punch────tag────setup
LOCOMOTION enter ── pace ────────── stop
GESTURE           beat    paw_raise
GAZE     audience ── Ella ── audience
REACTION              dead-stare
FACE      neutral ── annoyed ──── smug
```

---

## 8. Render Stack

```
Three.js + React Three Fiber + @pixiv/three-vrm + AnimationMixer

glTF Transform + Meshopt (normalization)

SkeletonUtils.retargetClip + vrm-mixamo-retargeter (humanoid retarget)

Mixamo + CMU Mocap + 100STYLE + Killella clips (motion seeds)

Three.js CCDIKSolver → closed-chain-ik-js (IK)
```

---

## 9. Data Flow

```
prompt + actual TTS word timings + body capabilities
        + Performance Engine + motion search
                ↓
            PerformancePlan
                ↓
            REAL STAGE RUNTIME
```

---

## 10. Sources

| Source | What to take | License |
|--------|-------------|---------|
| three.js SkeletonUtils | retargetClip, bone remapping | MIT |
| vrm-mixamo-retargeter | Mixamo → VRM, height scaling | MIT |
| @pixiv/three-vrm | normalized bones, expressions, VRMA | MIT |
| 100STYLE retargeted | style vocabulary + locomotion | CC-BY-4.0 |
| CMU Mocap BVH | general motion library | No restrictions |
| Adobe Mixamo | baseline rig + stock clips | Royalty-free commercial |
| glTF Transform | GLB canonicalization/compression | MIT |
| closed-chain-ik-js | runtime IK | Apache-2.0 |

### Do NOT use
- three.ws proprietary root runtime (use study only)
- ZeroEGGS data (noncommercial research only)
- LaFAN1 source data from Motion Matching (noncommercial)
