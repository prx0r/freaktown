# Runway — vendor brief (imported 2026-09-11)

Sources: https://docs.dev.runwayml.com/ (full dump: https://docs.dev.runwayml.com/llms-full.txt),
portal: https://dev.runwayml.com/models. SDKs: `@runwayml/sdk` (Node), `runwayml` (Py).
MCP available for Cursor/Claude/Codex. Playground for no-code tests.

## What it is

Task-based media API: create task → poll → output URL. One platform now hosts
first-party AND third-party models (Veo 3.1, Seedance, GPT Image, **ElevenLabs**
SFX/dubbing/STS endpoints — note the ElevenLabs overlap with our voice stack).

## Models that matter to us

| Model | Use | Price signal |
|---|---|---|
| **Character Video (GWM-1)** | speaking character from text script OR audio file — this is our "cinematic" tier directly | ~1 credit / 3s video + speech chars; price in credits at buy time |
| Gen-4.5 | text/image→video, up to 10s | $0.12/sec |
| Aleph 2.0 | in-context video editing, keyframe control | $0.28/sec |
| Act Two | motion capture | clips pipeline |
| Gen-4 Image (+Turbo) | stills/posters/share cards | from ~$0.01/image |

## ⚠️ Price check vs `renderers.py`

`renderers.py` lists `runway: cinematic ~$0.20`. At current list ($0.12/sec),
a full 60s Gen-4.5 minute ≈ $7 — so $0.20 only makes sense per short clip
(best-laugh ±10s ≈ $1–2) or via Character Video credits, NOT per full minute.
Do not wire spend caps from the $0.20 figure until re-quoted. Rule stands:
cinematic = clips and trailers, never full sets.

## Integration shape (matches our taskquet pattern)

```ts
const task = await client.imageToVideo.create({ model: 'gen4.5', promptText, ratio: '1280:720', duration: 5 }).waitForTaskOutput();
// or: POST /assets (frames) → POST /videos/create → GET /tasks/{id} → MP4
```

Async by design: fits the disposable-GPU-worker pattern (submit → terminate
poller → collect MP4 → R2). Go-live checklist + usage-exception requests exist
for scaling past self-serve tiers.

## Mapping to our tiers

`lam` free (local) → `bithuman` standard/expressive (realtime) → `runway`
cinematic (clips/trailers only). Unchanged architecture; only the price cell
needs re-quoting before any spend.
