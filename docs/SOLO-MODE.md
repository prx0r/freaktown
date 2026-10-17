# SOLO "CRACK ME" — face-cam vs the machine. SPEC (not built).

Status: SPEC ONLY, 2026-10-17. Nothing below runs yet. This doc is the
build contract; implement in slice order, demo each slice before the next.

## The minute

You open `/solo`. Your face cam turns on (opt-in 1). The machine reads
your taste (opt-in history or 3 calibration jokes). Then a comedian —
avatar on stage, voice in your ears — performs a set written LIVE to crack
YOU specifically. Your face is the scoreboard: hold a stone face and the
material gets sharper; smile and you're done. It records the set (opt-in 3)
and you get a share link to send friends: "it cracked me in 47 seconds."

## Why it works (the loop)

```
calibrate face ─> taste profile ─> generate line ─> perform (avatar+voice)
      ^                                                       |
      └──────── smile? CRACKED. hold? go sharper ────────────┘
```

The machine's goal is explicit: minimize your time-to-smile. Your goal:
survive. Both sides can see the score.

## Slices (build in order, demo each)

### S1 — Face gate (uses existing referee, ~1 day)
- Reuse `static/smile-referee.js` calibration + 0.82 threshold + 350ms poll.
- Crack rule: smile held across 2 consecutive polls (~700ms) = CRACKED.
  Glances don't count; sustained smiles do. Show a live "STRAIGHT-FACE"
  timer while performing.
- No new endpoints. No recording. Just: cam on → timer runs → smile ends
  it → " cracked in Ns" screen.

### S2 — Taste profile (local-first, ~1 day)
- Source A (no history): 3 calibration jokes (setup/punchline across
  absurdism, self-deprecation, deadpan). Which you smile at seeds the
  profile: `{mechanisms: {absurdism: 0.8, ...}, pace: normal|rapid,
  blue_ok: bool}`.
- Source B (returning): your past `/api/react` + smile rows (same device
  creator id) aggregated per mechanism/tag. Stored in localStorage only —
  never uploaded. Server never sees the profile; the client REQUESTS
  material ("more absurdism, no blue") and the server complies blind.
- Privacy consequence: taste never leaves the device. Say so in the UI.

### S3 — Live writer (mimo via Go, ~1-2 days)
- `POST /api/solo/write {wants: [mechanisms], avoids: [...], heat: 0-1,
  prior_lines: [...]}` → returns `{lines: [{text, mechanism}], model}`.
  heat = difficulty 0-1 (see S5).
- Rules: SETS LEAD applies to training, but solo lines are generated —
  keep them clean (no punching down, no blue unless blue_ok), max 25 words,
  one mechanism per line, callbacks reference YOUR earlier smiles.
- Fallback chain (Go is flaky — proven): mimo live → cached deck lines
  tagged by mechanism (ship 30 offline lines: 10/mechanism × 3) → never
  dead air. Every line carries `src: live|cached` so the UI can be honest.
- Cost: ~200 tokens/line on the owner's Go sub. Budget: 12 lines/night.

### S4 — Performance (existing stage, ~1 day)
- Lines render through the standard pipeline: TTS (edge-tts, free) →
  word offsets → acting timeline (expression/gesture/hold) → avatar +
  heat strip. Same player core as /perform rooms; solo skin on top.
- Voice: one fixed comic voice per run (consistency = character).
- The avatar watches back: while performing, the comedian's expression
  shifts with YOUR state (neutral while you hold, delighted glint when
  your smile-meter flickers — never the image, only the boolean).

### S5 — Difficulty + scoring (~1 day)
- Start heat 0.3 (gentle absurdism). Every 2 survived lines: +0.15 heat,
  callbacks unlocked, pace up. Smile = cracked: score = seconds survived
  + lines survived × 10 + difficulty bonus.
- Ranks (sticky, local): STONE (>120s), DEADPAN (>60s), CRACKED (<60s),
  GONE (<20s). Leaderboard is share-links, not accounts: your best crack
  clip IS the leaderboard entry.
- Anti-grind: same-mechanism spam caps at 3 — the writer must rotate.

### S6 — Record + share (~2 days)
- Opt-in 3 (separate screen, plain words): record the PERFORMANCE
  (avatar canvas + set audio). Face PiP is a FOURTH toggle, default OFF —
  most people share the machine losing, not their own face.
- Capture: MediaRecorder on the stage canvas stream + audio mix → webm →
  POST to takes-like storage → share URL `/s/<id>` (reuse takes infra).
- Share card: "The machine cracked [you] in Ns with [mechanism]" + clip.
  Friend opens it, watches, taps "BEAT THAT" → their own solo run.

## Data shapes

```json
// taste profile (localStorage only, never uploaded)
{"mechanisms": {"absurdism": 0.8, "deadpan": 0.6}, "pace": "rapid",
 "blue_ok": false, "cracks": 3, "best_s": 47}
// crack event (logged like any reaction)
{"slug": "solo", "reaction": "smile", "set_time_ms": 47000,
 "cond": "solo", "src": "face"}
```

## Acceptance (demo each slice)

- S1: 3/3 holds detected, 0 false cracks on talking/blinking, stop kills all.
- S2: cold start → 3 jokes → profile; returning device → profile loads.
- S3: 10 live lines, all clean, ≤1 fallback/night typical, src labeled.
- S4: line speaks <2s after generation, avatar moves, meter flickers.
- S5: full night ramps 0.3→0.9, crack ends it, score + rank shown.
- S6: shared link plays for a logged-out friend with zero setup.

## Out of scope (explicitly not this)

- Multiplayer solo (rooms already exist — different product).
- Server-side taste (privacy architecture forbids it).
- Paid TTS/voices (edge-tts free lane only until asked).
- Real-time model streaming (lines render whole, then speak — timing
  honesty over latency theater).
