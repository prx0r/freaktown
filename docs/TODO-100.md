# POGTOWN 100 — autonomous build backlog (Round 16, 2026-10-10)

Rule: sealed takes stay sealed; drafts stay drafts until a human laughs.
Money rule: $0 default. Tripo/GPU jobs need explicit human go. Owner pushes.

## A — Foundry ingestion bridge (characters/ -> our pipeline)
A01 delivery_to_take.py: delivery.json -> edge-TTS -> wav/timeline/cues/manifest
A02 Kyle audio take via bridge + timing QA vs plan
A03 Rhubarb phoneme cues for Kyle take
A04 Render Kyle on BASIC goblin body (no new mesh needed)
A05 QA+mux+publish Kyle as first studio guest set
A06 Ralph audio take (reptilian middle-management)
A07 Render Ralph on staged chimp GLB (rig-chimp + Jaw_M exist)
A08 Gnorma audio take + BASIC body render
A09 Fay audio take + staged butterfly GLB render
A10 Studio guest rail (takes dir, separate from sealed 13)

## B — DeityDB wiring (sourced premises)
B11 Entity-function map: functions -> premise seeds with citations
B12 Adapter --canon flag pulls domains/parallels/sources into draft provenance
B13 Ground canon/hermes from DeityDB Hermes row
B14 Psychopomp bill draft: Sesh + Hermanubis + Charon
B15 verify_against checker: every canon trait traces to a source row
B16 Reception-chain premises (one figure, three traditions, one stage)
B17 Cross-tradition parallels report for the 6 active mechanisms
B18 Almanac extracts stay research-only: lint rule + doc
B19 IP eyeball: Britt-Nordic, Charlie, Buddha billing review
B20 Canon expansion queue: next 6 from 137 traditions, ranked

## C — Bodies & rigging (first Tripo job on human go)
C01 Confirm Tripo key + balance, rig-check 3 staged meshes (free)
C02 Kyle frog body: Tripo image-to-3D + quadruped rig ($0.55)
C03 Retarget 5 motions onto Kyle frog ($0.50)
C04 Import Kyle rig into pipeline (atlas_intake + blender_factory + puppet_qa)
C05 Render Kyle take on his own body, A/B vs BASIC-body version
C06 Mesh2Motion manual rig trial for one hero (Nolan candidate)
C07 SkinTokens trial design (needs rented 24GB GPU — human go first)
C08 Face-yaw + scale catalog for all 13 staged meshes
C09 Body acquisition queue doc (who needs what, cost each)
C10 Retire procedural placeholders where real bodies land

## D — Performance & lipsync
D01 Rhubarb cues onto cat/chimp/nature sealed takes (jawed trio)
D02 Re-render Peel with phoneme jaw, A/B vs envelope version
D03 Replacement-mouth v0: one prebuilt mouth plate on one character
D04 Blink pass: procedurally driven where eye bones/morphs exist, audit where not
D05 Emphasis retune from timing evidence (energy-scaled nod amplitudes)
D06 Punchline-hold calibration per voice (measured TTS trailing silence)
D07 Entrance variety (walk-in vs rise-in vs already-on-stage)
D08 Mic prop scale/placement audit across framings
D09 Settle + overshoot parameters per movement family
D10 Motion-style profile per P0 character (pog.motion-style.v1 rows)

## E — Comedy engine (theory -> stage)
E01 Mechanism template banks for all 9 direction mechanisms
E02 Trojan-horse weaver: joke-joke-THEORY-tag-closer assembly
E03 Figgsite JokeBlock import (blocks dir -> premise candidates)
E04 Evaluator priors seeded from mined theory JSON
E05 First audience belief update once 5+ eligible views exist
E06 Second-set proof: new premise -> adapter -> take -> studio
E07 Blind A/B protocol doc (same block, two deliveries, human picks)
E08 Critic pass v0: blind-viewing checklist generator from timeline
E09 Writers-room scheduler sketch (observe->angles->premises->write->rehearse)
E10 Exhaustion model: exact/premise/mechanism/cliche counters in graph

## F — Studio product
F01 KEEP/CUT verdict buttons on player (writes feedback.verdict)
F02 Server-side judged memory (per-viewer progress, survives devices)
F03 Share links per set (?s=slug, no token in URL)
F04 Mobile layout pass (thumb-reach POG, big targets)
F05 Loading + error states (failed video, failed press, retry)
F06 Keyboard shortcuts help line (p = POG, n = next after submit)
F07 Guest-vs-sealed rails on /sets
F08 Finale screen (all judged: totals + strongest bits)
F09 Comment prompt rotation (what landed / what died / who is this for)
F10 No-store + version stamp so stale pages never recur

## G — Audience & distribution
G01 Shows site guest section (Kyle + next guests)
G02 R2 upload script (mp4/webm/poster/hls per take, one command)
G03 Feed page (all sets, newest first) for agent + human browsing
G04 OG cards per set (poster + premise as title)
G05 Public POG-loop design (rate limits, anti-spam, eligible-view rule)
G06 Vote aggregation job (reactions -> nightly summary)
G07 YT-comment-format exporter (feedback -> upload-ready text)
G08 Best-20s clip cutter per set (plan + ffmpeg)
G09 Vertical shorts metadata (title/hashtags from premise)
G10 First public post checklist (authorize, post, log post_ref)

## H — Quality & QA
H01 Re-render remaining 12 with v3 cameras (batch, background)
H02 Contact-sheet review pass 2 (all v3 framings)
H03 QA thresholds doc (what PASS means per metric)
H04 Golden renders: 4 benchmark fixtures for regression
H05 Loudness normalize across takes (single integrated target)
H06 SRT timing audit (cue drift vs timeline)
H07 Poster refresh for re-rendered sets
H08 WebM+HLS for every new take (mux script enforced)
H09 Frame-diff pose metric fix (0.0 readings are a metric bug, not stillness)
H10 Retire v1 MP4s only after human confirms v3s

## I — Ops & hardening
I01 serve_p0.sh systemd unit (survive reboot)
I02 Tunnel config backup job (nightly snapshot of remote ingress)
I03 Disk cleanup (80% full: frame dirs, dup caches, old venvs)
I04 Evidence backup to R2 (reactions/feedback nightly, hash-chained)
I05 Health dashboard (studio/tunnel/R2 one glance)
I06 Render queue lock (one Blender at a time, FIFO)
I07 Cost ledger (every API/GPU cent per character)
I08 Secret rotation checklist (pasted keys, token files)
I09 Stale-cache purge runbook (the double-brace incident notes)
I10 Owner-push packet builder (diff + test report + H10 signoffs)

## J — Canon & characters
J01 Ground hermes canon from DeityDB row + parallels
J02 Ground charon + iris rows for psychopomp bill
J03 Hekate canon draft (retinue included)
J04 Mantis/gray/mib canon review (which earn performers next)
J05 Ralph trio bill: Ralph + Doug + Rudy one stage, one night
J06 Psychopomp bill: Sesh + Hermanubis + Charon
J07 Kyle guest billing copy (premise + callback hooks as tout)
J08 Voice casting for Kyle/Ralph/Gnorma/Fay (edge picks + why)
J09 Mesh guide per active canon (body, fallback, rig path)
J10 Roster v2 doc (P0 13 + 4 guests + bills)
