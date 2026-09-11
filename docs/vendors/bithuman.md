# bitHuman — vendor brief (imported 2026-09-11)

Sources: https://docs.bithuman.ai/ (full agent index: https://docs.bithuman.ai/llms.txt),
SDK: https://github.com/bithuman-product/bithuman-sdk-public (ships its own AGENTS.md).
LiveKit: https://docs.livekit.io/agents/models/avatar/plugins/bithuman

## What it is

Realtime lip-synced avatars: audio in, talking video out at 25fps, sub-200ms.
One `.imx` format + one SDK shape across every surface. Directly relevant: a
**LiveKit plugin** exists (`livekit.plugins.bithuman.AvatarSession`) — drops
into the LiveKit agent path our P2 plan already uses.

## Models (pick per use, not per vendor)

| Family | Input | Compute | Use for us |
|---|---|---|---|
| Essence 1/2 (+2-max) | pre-built `.imx` identity (built once from a photo) | any CPU (2-max: cloud GPU, hero quality) | resident club cast, cheap always-on |
| Expression 1/2 | ANY portrait at runtime, no build step | GPU (or Apple Silicon M3+) | one-off/user-uploaded faces, close-ups |

Gen-2 (essence-2, essence-2-max, expression-2) GA since July 2026. Custom
gestures (wave/nod/laugh) on Essence; AI micro-movement on Expression.

## API (all behind `api-secret` header, base `https://api.bithuman.ai`)

- `POST /v1/validate` — free credential check, no credits.
- `POST /v1/agent/generate` — create from prompt/image (`model: essence|expression`,
  `version: v1|v2`); returns agent code (e.g. `A91XMB7113`).
- `GET /v1/agent/status/<code>` — poll until ready (expression-2 trains
  ~2h per identity — batch this, never inline in a user flow).
- Speak / add-context / gestures / file upload / short-lived streaming JWTs.
- TTS built in: 31 languages, 10 voices. Python SDK: `pip install bithuman`
  (+ `bithuman-cli` separate wheel since 2.3). Never check the secret into git;
  browser embeds use the embed-token flow, not the secret.

## Pricing (credits; verify at buy time)

- One-time generation: v1 250 · essence-2 500 · expression-2 2000.
- Live minutes: essence self-hosted 1/min · cloud 2/min (expression higher).
- Free plan: 99 credits/mo, 10 conversation min/mo — enough for a trial lane.

## Mapping to our `renderers.py` tiers

`bithuman-essence` ($0.006–0.012) ≈ Essence cloud minutes; `bithuman-expression`
($0.012–0.024) ≈ Expression. Router shape holds; re-verify exact per-minute
costs before wiring spend caps. Freak Pack avatar refs stay provider-neutral
(`avatar.json` manifest) — bitHuman is one filler of that slot.
