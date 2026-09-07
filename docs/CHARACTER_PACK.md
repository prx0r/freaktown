# Freak Character Pack — Canonical Spec v1

> One folder = one freak. Everything a character needs to be created,
> rehearsed, performed, and handed to the live show. Every field except
> `character.json: name` is optional — packs degrade gracefully.

## Layout

```text
freaks/<slug>/
  character.json       # identity, persona, voice, performance profile (REQUIRED: name)
  avatar.vrm           # canonical performer body (optional)
  avatar.json          # capability contract, REQUIRED if avatar.vrm present
  voice_reference.wav  # cloning source, 3-10s clean speech (optional)
  portrait.png         # 2D concept art (optional)
  visual.json          # portrait recipe: model, seed, prompt, traits (optional)
  delivery.json        # performance score, freaktown.delivery.v1 (optional until first set)
  set.wav              # composed clip with exact silence (optional until composed)
  walkout.wav          # entrance sting (optional)
  walkout.json         # walkout recipe: genre/mood/energy/shape/seed (optional)
  meta.json            # status, file hashes, timestamps (auto-maintained)
```

Rules:
- `avatar.vrm` is canonical. `avatar.glb` is accepted as a legacy import
  and should be converted, never required.
- No field may contain secrets. Keys live in env/vault, never in packs.
- `meta.json` is written by tooling, not by hand.

## character.json

```json
{
  "name": "No-Nose Nolan",
  "species": "dog",
  "premise": "Police sniffer dog born without a sense of smell",
  "vibe": "anxious",
  "voice": {
    "provider": "edge-tts",
    "voice_id": "en-US-GuyNeural",
    "reference_audio": "voice_reference.wav"
  },
  "persona": {
    "deal": "Thinks every other dog is sexually obsessed with him because they keep sniffing his ass.",
    "facts": [
      "cannot smell anything",
      "somehow passed police training"
    ],
    "interview_style": "defensive, earnest, spirals when contradicted"
  },
  "profile": {
    "pace": 0.94,
    "movement": 0.4,
    "eye_contact": 0.8,
    "energy": 0.65,
    "punchline_hold_ms": 850,
    "gesture_frequency": 0.3
  }
}
```

- `vibe` seeds `profile` from the vibe table (`/api/profile`); stored here
  so the pack is self-contained and the table can evolve without rewriting packs.
- `persona.facts` is interview fuel, not script. The interviewer discovers
  contradictions from facts; the comedian never recites them.
- `voice.reference_audio` points at `voice_reference.wav` when present.
  Without it, `voice_id` is used as-is.

## avatar.json — capability contract

The runtime asks what the body **can do**, never assumes. A blob with only
a mouth is a valid performer if it declares so.

```json
{
  "version": "freaktown.avatar.v1",
  "format": "vrm",
  "vrm_version": "1.0",
  "asset": "avatar.vrm",
  "capabilities": {
    "humanoid": true,
    "blink": true,
    "visemes": ["aa", "ih", "ou", "ee", "oh"],
    "look_at": true,
    "expressions": ["happy", "angry", "sad", "surprised", "relaxed"]
  }
}
```

Capability rules:
- `visemes: []` → mouth stays shut; character performs through timing + expression.
- `humanoid: false` → no body gestures; only `hold still` and face (if any).
- `blink: false` → blink timer disabled, no error.
- `expressions` lists exactly the VRM preset names present. Unknown names
  in delivery are ignored, never crash.
- `look_at: false` → gaze cues collapse to `hold still`.

## actions — what the character DOES

Actions are named, reusable, triggerable behaviors. They sit between the
delivery score and the raw motion vocabulary: delivery references actions,
actions resolve to capabilities, capabilities degrade per the contract above.

```json
{
  "actions": {
    "nolan_stare": {
      "trigger": "after_punchline",
      "tags": ["reaction.dead_stare", "gaze.audience"],
      "face": "deadpan",
      "body": "hold still",
      "requires": {"humanoid": false, "blink": false, "visemes": []},
      "fallback": "hold still"
    },
    "pigeon_flinch": {
      "trigger": "on_groan",
      "tags": ["reaction.flinch", "gaze.away"],
      "face": "surprised",
      "body": "small gesture",
      "requires": {"humanoid": true, "blink": false, "visemes": []},
      "fallback": "hold still"
    }
  }
}
```

- `trigger` vocabulary (closed set for v1): `on_enter`, `after_setup`,
  `after_punchline`, `after_tag`, `on_laugh`, `on_groan`, `on_silence`,
  `before_closer`, `after_closer`, `on_exit`, `manual`.
- `tags` use the motion-language vocabulary (`reaction.*`, `gaze.*`,
  `gesture.*`, `locomotion.*`, `pose.*`, `face.*`). Tags a body can't
  perform resolve through `fallback`, which must itself be resolvable
  (ultimately `hold still`, which every body supports).
- `requires` declares the minimum capabilities; if the avatar contract
  doesn't satisfy them, `fallback` runs instead. No errors, ever.
- `face`/`body` reuse the exact editor vocabularies so what you direct
  is what performs:
  - face: `neutral, deadpan, grin, annoyed, confused, surprised`
  - body: `normal, hold still, lean in, look left, look right, shrug, small gesture, big gesture`
- `manual` actions are buttons, not automation: rimshot-point, bow,
  mic-drop. The performer (or Ella) fires them live.

Where actions live: `character.json` holds an `actions` object for the
character's signature moves (empty `{}` is fine). Per-set one-offs live
in `delivery.json` beats via `performance.expression/gesture`, never in
the character file.

## delivery.json

Unchanged: `freaktown.delivery.v1` — `profile{}`, `voice{}`, `beats[]`
with `speech{pace, emphasis}`, `performance{expression, gesture, look}`,
`pause_after_ms`. See `schemas/delivery_v1.json`.
Beat `performance.expression/gesture` values must come from the vocabularies
above so any avatar contract can resolve them.

## meta.json (tool-written)

```json
{
  "slug": "no-nose-nolan-a1b2c3",
  "status": "draft",
  "created_at": "2026-09-07T20:00:00+00:00",
  "updated_at": "2026-09-07T20:05:00+00:00",
  "submitted_at": null,
  "files": {
    "character.json": "sha256:…",
    "delivery.json": "sha256:…",
    "set.wav": "sha256:…"
  }
}
```

- `status`: `draft` → `ready` → `queued` → `performed`. Only forward.
- `ready` means: character.json valid + delivery.json valid + set.wav present
  and hash-matched. The live show refuses anything else.
- `files` hashes every file except `meta.json` itself. Hash mismatch on
  load = corrupt bundle, refuse with a reason, never perform garbage.

## Validation

`scripts/validate_pack.py <freaks/slug>` checks the whole contract and
exits non-zero with reasons on failure:

1. `character.json` parses, has `name`.
2. If `avatar.vrm` present: `avatar.json` present, valid contract shape.
3. If `delivery.json` present: version `freaktown.delivery.v1`, beats have
   text, expression/gesture values inside vocabularies.
4. If `set.wav` present: valid WAV header.
5. `meta.json` hashes match actual files (when status is `ready` or beyond).

## Degradation table

| Missing | Result |
|---------|--------|
| avatar.vrm | Audio-only performance. Stage shows portrait or placeholder. |
| avatar.json (but vrm present) | Invalid pack. Refuse until contract exists. |
| voice_reference.wav | `voice_id` used directly. No cloning. |
| delivery.json | Character exists but has never performed. Not submittable. |
| set.wav | Recompose from delivery on demand. |
| walkout.* | Silence before entrance. |
| portrait.* | Placeholder avatar card. |

## Non-goals for v1

- No joint angles, no bone names, no keyframes in packs. Ever.
- No per-frame animation data. Beats are the smallest addressable unit.
- No secrets, keys, or absolute paths. Packs must be portable across machines.
