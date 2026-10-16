# archive/ — retired, not deleted

Everything here was runnable and green at archive time (2026-09-11) but is
superseded by an authoritative implementation elsewhere. Kept for provenance;
not imported by serving code; not run by CI.

## Dormant Python game engine → superseded by pogtown (prx0r/pogtown)

| Archived | Authority now |
|---|---|
| `game_runtime.py` + `test_game_runtime.py` | pogtown `packages/runtime/runtime.mjs` (serving, Docker) |
| `format_runtime.py` + `test_format_runtime.py` | pogtown `packages/game-pack/` (5 validated packs) |
| `sdk.py` + `test_sdk.py` | pogtown `services/agent-gateway/` + freaktown `sdk.py` consumers moved |
| `formats/` (comedy.open-mic, poetry.slam) | pogtown `games/` |
| `game-packs/` (mafia.freak-game.json) | pogtown `games/mafia/` (game truth lives there) |
| `scripts/freak_format.py`, `sdk_demo.py`, `e2e.py` | pogtown `scripts/demo.mjs`, `healthcheck.mjs` |

Last green receipt: 27 passed (`test_game_runtime` + `test_format_runtime` +
`test_sdk`, 2026-09-11, before archive). Serving code (`app.py`, `party.py`,
`backend/`) never imported these — verified by grep, so removal changes no
live behavior. Rule going forward (see `docs/BOUNDARIES.md`): game truth is
implemented exactly once, in pogtown. Freaktown consumes it via the
stage-adapter; it never reimplements it.
