# Killella import — migration record

Direction: **Killella into Freak Town.** Freak Town is product + contracts;
imported code is execution infrastructure. See `devplan.md` §2 (ownership)
and `docs/BOUNDARIES.md` (to be added).

## Baselines

```text
FREAKTOWN_SOURCE (pinned)  e8a6eabfd2718bf6462d10e7b89aa66d795cd68a
  tag: pre-killella-merge-e8a6eab (pushed)

KILLELLA_SOURCE (pinned)   863cdd37f73436f7ee5118b82340731eb868bf09
  tag (killella repo, local only): frozen-before-freaktown-merge-863cdd3

Actual branch point        f354306 (main: merge-prep + ship debug-flag fix)
Branch                     merge/killella-infra
```

History attached via `merge -s ours` (parent 2 = killella/main, tree unchanged).
Source worktree: `../killella-source` (temporary, removed at migration end).

## Deviation log

1. Branch point is f354306, not e8a6eab: the merge-prep work
   (offsets.json, submit-to-intake forwarding) and the ship debug-flag fix
   are required by the migration. e8a6eab is tagged for exact reproduction.
2. `delivery.v1` canonical shape (§8 of devplan) NOT yet applied: current
   prod bundles use `speech{}`/`performance{}` blocks and intake accepts
   them. v1 is frozen as-is; the canonical `delivery{}`-block shape becomes
   `freaktown.delivery.v2`, never a silent v1 mutation. Golden fixture pins
   current v1.
