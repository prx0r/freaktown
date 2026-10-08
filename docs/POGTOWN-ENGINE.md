# Pogtown engine — figgsite ↔ freaktown contract

Two repos, one system. Figgsite mines what's funny; freaktown performs it.

## Figgsite owns (upstream)

- JokeBlocks (`figgsite/templates/blocks/`) — append-only reality+culture dossiers.
- Theories + world operators (`templates/theories.json`, `backend/creative/world_ops.py`).
- Premises, derivations, comics packs; public-domain cast + archetypes + evergreen tree.
- ComedyJudge (pairwise + vetoes + ledger taste), classifier, regulars scoring.
- Ledger (`data/meme_performance.jsonl`, `data/comedy_prefs.jsonl`) — social engagement + duel votes.

Docs: `figgsite/docs/comedy-os.md` (inventory), `joke-blocks.md` (ontology),
`theory-bank.md`, `comedy-graph.md` (full spec, verbatim), `meme-engine.md`.

## Freaktown owns (downstream)

- `comedy/` compiler: corpus → rhythms → director → delivery.v1 → evaluator.
- Characters as `freaks/<slug>/` packs (`docs/CHARACTER_PACK.md`).
- Voices in `data/voice-bank/<voice-id>/` (`docs/VOICE-BANK.md`).
- Stage, sets, audience, reactions.

## The joints

| Figgsite | Freaktown | Rule |
|---|---|---|
| premise (theories + oppositions) | `director.py` input | premise carries everything needed to cast + time it |
| theory support scores | `evaluator.py` mechanism stats | same question, material vs delivery layer |
| regulars (fertility + callbacks) | recurring cast | empirically discovered, never assigned |
| ledger engagement | evaluator training | social signal + stage signal stay separate columns |
| `actor_id` (`pog.*`) | `freaks/<slug>/` | one id across stage, news, games, merch |
| CharacterGraph | freak `character.json` | beliefs/desires/blindspots/memories port as persona fields |
| voice fingerprints | voice profile | rhythm/habits/triggers travel; audio stays replaceable |
| public-domain cast registry | acquisition queue | allowed-traits + jurisdiction gate every download |

## Roster

Canonical cast: `docs/POGTOWN-ROSTER.md` (10 primary + 10 wider, acquisition order, voice rules).
Existing stage cast: `CAST.md` (19 acts — predates the PD policy; migrate gradually, don't purge).
