# Director vocab (per-character staging words)

Pattern credit: mutuals-inc/character-harness (Apache-2.0) —
`extensions/director` (vocab-constrained LLM staging + per-reply
budgets) and `extensions/emotion-tags` (instant face from `[tag]`
openers, no model call). Their runtime is NOT adopted (paid providers,
Kaigen player); the vocab contract is, mapped onto our beat bus.

## What we took

- **`backend/services/freaktown/director_vocab.py`** — `director.json`
  per freak: emotions with acting hints, `[tag]`->emotion synonyms,
  intense list, gestures/cameras/registers, per-reply limits.
  `beat_emotion()` resolves a beat's face: tag opener wins, else the
  authored expression. `Budget` caps intense/camera spend per reply.
- **Take build** (`scripts/delivery_to_take.py`) applies the tag
  override into `timeline[].performance.expression` (marked
  `expression_source: delivery_tag`); unmapped tags change nothing.
- **Example**: `docs/DIRECTOR.example.json` (kappa-kyle). Copy to
  `<freak>/director.json` and edit.

## What maps where (their extension -> our equivalent)

| Mutuals | Freaktown | Note |
|---|---|---|
| emotion-tags (`[tag]` -> face at sentence start) | `beat_emotion` + stage beat expressions | Same instant rule; ours resolves at take build, theirs at speak time |
| director (LLM stages beats in-vocab, budgeted) | `motion_compiler` (authored) + take `performance.*` | When an LLM director writes beats, constrain it to the vocab file; budgets already match |
| reactions (judge line -> opening face/gesture + settle mood + laugh) | `ReactionPolicy` + `resolve_expression` + Omni `emotion` override | Same three slots (reaction/settle/laugh); theirs is conversational text, ours is room energy + prosody |
| memory (forest store, need/cost, out-of-date, user's words) | — (gap) | Best next port for interview continuity (Ella x freak): adopt store shape, keep our providers |

## Not adopted

Kaigen player (licence; our stage is Three.js), ElevenLabs/xAI/Typesafe
providers (paid; our stack is $0 — hook shapes fit either).
