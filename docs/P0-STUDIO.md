# P0 studio — the laugh-capture loop

Sealed minutes (Mode A) + human POG presses + post-show feedback as a proxy
for YouTube comments/engagement. Live: `https://www.pogtown.com/p0/`
(served by the figgsite tunnel's `/p0/*` path rules; the shop root is untouched).

## Human loop

1. Open `/p0/` — first unjudged set loads, big screen.
2. Press **POG** (or `p`) when you laugh. Stored per `schemas/pog.reaction.v1.json`
   (`set_id, viewer, kind, playback_ms, wall_ms, origin`) with `beat_id`
   resolved server-side from `timeline.json`. `origin` is always `audience` for you.
3. When it ends, write feedback, Submit — next unjudged set autoloads.
4. After a session: `python3 scripts/p0_learn.py` (dry run) then `--apply`
   to write `notebook.json` facts + `policy.json` evidence rows.
   `human_laughter` stays null until ≥1 eligible view; critic QA is never laughter.

## Agent protocol

Sets are machine-readable: `GET /api/p0/sets` (character, premise, mechanisms,
intent, lines, beats, video flags), per-set `timeline.json` / `set_plan.json`
on disk, `/api/p0/summary/<set>` for the laugh curve + strong/weak bits.

Agents may watch and judge too, with one hard rule: **`origin: rehearsal`**,
never `audience`. Human presses are L (real laughter); rehearsal presses train
only mechanism stats. Example:

```
POST /api/p0/react  {set_id, kind: POG|HAHA|CLAP, playback_ms, viewer: <agent>, origin: rehearsal}
POST /api/p0/feedback  {set_id, viewer, comment, funniest_ms, replay_intent, share_intent, want_more, verdict}
```

Writes need the backend-held token (`X-P0-Token`, injected into served pages —
never in URLs). Reads are public; the MP4s are already on the shows site.

## Generation path (sealed takes)

```
premise -> scripts/premise_to_lines.py [--polish] -> human review -> p0-sets.json
  (polish tried 2026-10-10, hermes3:8b local: 15 lines for 6, refused by guardrail)
  -> scripts/build_set.py (lines -> delivery.v1 -> edge-TTS -> wav/timeline/cues)
     (run with PYTHONPATH=. from the repo root; the scripts assume it)
  -> scripts/render_set.py (Blender; --mouth mouth_cues_rhubarb.json on jawed sets,
     --face-yaw 180 for backwards models, close-ups punchline-only)
  -> scripts/puppet_qa.py -> scripts/p0_mux.sh (faststart mp4 + webm)
  -> R2 shows site + studio watch
```

Honest limits: lines are human-written (adapter drafts, human promotes);
mouths are envelope flap, Rhubarb phonemes on jawed sets only; 10/13 sets have
no jaw/morph (whole-body fallback by design). Cost per take: $0 (edge-TTS,
Blender CPU, local Ollama polish).
