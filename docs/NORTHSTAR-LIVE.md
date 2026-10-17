# NORTHSTAR-LIVE — the venue is real when all three are true (2026-10-17)

Checked autonomously by `scripts/watch_performance.py` (Jev eyes). No human
"looks fine" — probabilities or it didn't happen.

## Gate 1 — THE SPLAT IS LIVE
A Marble-derived mesh fills the stage page (not a view-box, not CSS).
Threshold: `room_rendered >= 0.85` AND mesh asset pinned in venue JSON.
Status: TRUE (2026-10-17: room 0.98–0.99 across 5 watches; 33MB GLB pinned
tavern-test `3d85da49c8846d48`). Cauldron pending its mesh.

## Gate 2 — THE PERFORMER IS ON SCREEN
A VRM body stands at the mic mark, visible to the watcher.
Threshold: `performer_on_stage >= 0.7` AND `performer_box` non-degenerate.
Status: TRUE (2026-10-17: 0.96–0.99 stable, box [0.44–0.57]x[0.43–0.70]
identical across frames). Fixed en route: SwiftShader/ANGLE MToon+spot-
shadow compile failure (shadows off, P0), bogus rotateVRM call removed.

## Gate 3 — THE SET IS DELIVERED
Full set audio plays in-room; face moves with it (beat expressions now,
phoneme lipsync later); PLAY SET completes without error text.
Threshold: set completes AND `page_error <= 0.2` on final frame.
Status: TRUE (2026-10-17: biscuit 10 beats, 62.6/62.6s played, jaw slot
`aa` live via energy flap, zero page errors, end-frame error 0.03).

## Rules
- Watcher verdicts are the only scoreboard. Fix, re-watch, compare numbers.
- Never claim a gate without a fresh watch log.
- Spend rules stand: Jev judgments (~$0.0001/cycle) are pre-approved micro-
  spend; FAL/Atlas live calls always need explicit owner yes.
