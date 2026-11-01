# UNC'S VERSE OF THE DAY — show spec (draft)

Status: PROPOSED. Pilot: one episode (v5 roadman), fast route first.

## 1. Concept

A roadman ex-preacher (Unc) does 30–60s daily verses into a club mic: one killer
line cold open, one verse in full roadman C2, Sanskrit flash, bless-out. Devotion
with the ends' cadence — never parody, always sourced (every line traces to a
gated canonical packet; see ipvv `site/data/c2/`).

Why it works: the character's joke (washed unc reads scripture) is the delivery
vehicle, never the target. The verse is always treated straight.

## 2. Character spec

| Field | Value |
|-------|-------|
| Name | Unc |
| Slug | `unc-verse-of-day` |
| Premise | Ex-roadman, too old for the roads now, reads Trika scripture to the mandem into a club mic |
| Body | human, mic in hand, COMIC_CLOSE |
| Voice | en-GB male edge-tts (free, today). Shortlist: en-GB-RyanNeural / en-GB-OliverNeural — pick by table-read |
| Deal | Knows every verse by heart, misplaces his glasses; calls Death "unc" back; ends every set with "Bless up" |
| Facts | retired from road (unc status, certified) · carries one book (the stotra) everywhere · cannot work the smoke machine · beef with the club's playlist (wants tanpura) |
| Minute | The MANDEM wake-up call (filed: ipvv `site/data/c2/roadman-opening.json`) — cold open, dismissal of sleep, divine proximity, call + response |

Character home: Characters MCP (PR #8) once conflicts resolve. Until then: plain
dict in `comedians.py` (same shape as Nolan et al.), TTS via `show.py`.

## 3. Episode format (30–60s)

1. **Cold open (0–5s):** killer line straight to lens. v5: *"Man don't feel fear, innit."*
2. **The verse (5–35s):** full roadman C2, lip-synced, captions burned in.
   v5: *"So yeah — lights on, darkness gone… One bless up to the Lord and they're done. I don't do fear. Ever. Bow."*
3. **Sanskrit flash (35–45s):** Devanagari card + one-line payload.
   v5: *"namas: the salute is the whole defense."*
4. **Bless-out (45–50s):** *"Bless up. Tomorrow, same time."* End card: work · verse · gate.

## 4. Season 1 backlog (11 episodes, all written)

| # | Material | Register | Status |
|---|----------|----------|--------|
| 0 | MANDEM wake-up call (prabodhana) | roadman | filed |
| 1–10 | bhairavastava v1–v10 | roadman | filed (`bhairavastava.roadman.json`, all PASS-verified) |

Gen-z set (`bhairavastava.gen-z.v2.json` + killers) is the series-2 voice
(same show, second register — never blended in one episode).

## 5. Technical plan

| Need | Source | Status |
|------|--------|--------|
| Mic format (acts, sketches) | PR #6 (MERGEABLE — needs `slug` KeyError fix + espeak in CI) | fix-then-merge |
| Camera kit + face guarantee | PR #13 (MERGEABLE, presets pass incl. basement-open-mic) | merge after #6 |
| Character home (persistent Unc) | PR #8 (CONFLICTING, 8 files in apps/live) | rebase + resolve |
| Club venue (Blender set) | PR #11 (MERGEABLE, 44K lines mostly generated) | optional for pilot — defer |
| Voice | edge-tts en-GB male (free, in-repo pattern) | ready |
| Captions/Sanskrit cards | aoc 9:16 slideshow renderer (proven) or stage captions | decision needed |
| Music bed | tanpura/drone loop, licensed or generated | open item |
| Gate | only PASS-gated verses render; label `machine rendering` on C2-derived lines | enforced in content, not code (v1 scope) |

**Fast route (days):** `show.py --comedian unc-verse-of-day` → edge-tts wav →
aoc renderer captions → human approve → post. No Blender, no MCP.
**Full route (weeks):** GLB avatar (Meshy rig like Buddha demo) → `face:check` →
COMIC_CLOSE stage set → lip-synced episodes.

Recommendation: fast-route pilot = v5 episode. Avatar stage iff format lands.

## 6. Pipeline (mirrors aoc gated flow)

```
C2 file (ipvv/site/data/c2/*.json)
  → script card (killer + verse + flash + bless-out, refs to chunk ids)
  → voice (edge-tts, fixed voice id — no per-episode recasting)
  → render (9:16 captions; Sanskrit big, translation timed)
  → music bed mix
  → HUMAN APPROVE (no auto-post, ever)
  → post + receipts (episode ↔ chunk id logged)
```

## 7. Open questions for owner

1. Name locked as **Unc**? (alternates: Mandem Marcus, the Slangskrit Preacher)
2. Voice: male (default) or female read? Table-read both edge-tts en-GB voices.
3. Music: license-free drone loops, or generate beds?
4. Account: new channel for this (Roadman Sanskrit free; slangskrit taken)?
5. Cadence: daily for 11 episodes, then series 2 (gen-z voice)?
