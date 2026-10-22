# SHOW RUNTIME — Cauldron live show backend (funnier `cauldron_show.py`)

One performer comes out (walkout sting), does their minute, then gets
interviewed by Killella. The audience laughs with buttons; agents laugh
with HTTP. The stage (other agent's lane) renders; this module is the
clock, the record, and the verdict. No stage markup here on purpose.

## Ideas stolen (with love)

- **killella backend**: the phase machine (`preshow → ella_intro → act →
  return_vote → ella_outro → ended`), per-act laugh timeline `[{ms,count}]`,
  judge panel with asymmetric info, interview engine with structured state.
- **pogtown**: `runtime/importBundle` (bundles are validated on load, never
  trusted), `games/standup` (a set is beats + audio + duration), agent
  access over plain HTTP like `agent-gateway`.
- **funnier**: laugh economics — `POST /laughs {clip, t, device}`, 1-second
  histogram, each laugh +0.15 of a vote capped at 1.0, agents vote through
  the same API as humans.
- **characters2**: the performer bundle — `character.json` (persona),
  `delivery.json` (beats: text + performance + speech), `set.wav`,
  `show.json` (`schema: pogtown.show.v1` — walkout/win/loss stings with
  `audio_path` + `duration_ms`, entrance direction), `meta.json`
  (`status: ready`, voice).
- **funnier**: the KILLED bars (energy ≥ 12, coverage ≥ 0.5, ≥ 3 distinct
  tappers, ≤ 1 boo) and host-driven rooms (`host_token`).

## Bundle link

`SHOW_PERFORMERS_DIR` (default `/root/characters2/freaks`). `list_ready()`
reads every `*/meta.json` with `status == ready`. Audio is best-effort:
`set.wav` under 100KB counts as a stub (served, flagged); sting paths from
`show.json` resolve against the bundle dir, then `characters2/audition`,
then `characters/audition/audio`; missing stings are `null`, never errors.
TTS voices for interview answers are a render step, not runtime.

## Phases (per act)

`GREEN_ROOM → INTRO → SET → INTERVIEW → VERDICT → (next act | ENDED)`

Host-driven (`POST /api/show/<code>/advance`) — the room never waits on
audio or the model; a missing sting or a dead key degrades to text, never
a wedge. This is the killella lesson (control plane, not a live socket)
and the party lesson (host owns the clock).

## Endpoints (all JSON; stage polls `GET /api/show/<code>`)

- `GET /api/show/performers` — ready slugs + name/voice/beat counts.
- `POST /api/show/create {performers:[slugs], venue}` — `{code}`.
- `POST /api/show/<code>/start` — act 1 `INTRO`.
- `POST /api/show/<code>/advance` — next phase (host only).
- `GET /api/show/<code>` — full state: phase, act, bundle meta, delivery
  beats, audio urls + stub flags, laugh totals + 1s histogram, interview
  transcript, verdict.
- `GET /api/show/<code>/audio/<kind>` — `set|walkout|win|loss`, 404 when
  the bundle has none (stage falls back to text timing from delivery).
- `POST /api/show/<code>/laugh {t, type, device}` — the laugh track.
  Anonymous device ids like funnier (one id per phone; agents use seat
  names). Counted into the act timeline and the verdict math.
- `POST /api/show/<code>/interview {text?}` — next interview turn. Dry by
  default (Killella asks from a deck built on the set's beats — $0, no
  network); live when `PARTY_PI_AGENTS=1` (Killella persona via Qwen,
  performer answers in its character.json voice — capped at
  `SHOW_INTERVIEW_TURNS`, default 3 exchanges).
- `GET /api/show/<code>/verdict` — crowd (KILLED math on this act's
  laughs) + judge (live scores or `pending`) + sting pick (win iff killed).

## What this is NOT (v1 limits)

No SSE (stage polls; party's `/stream` is the pattern if polling hurts).
No TTS in the loop (interview is text; Fish/edge render the transcript
after, same as takes). No new bodies or cameras (stage lane). Win/loss
sting rule is the v1 KILLED bar, tunable via env, not a critic.
