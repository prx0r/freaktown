# PogDirector + PogCritic — intention → performance → observed interpretation

Saved 2026-10-08. Voice and timing are the highest-leverage performance
controls, and the performance agent must model what the audience
believes at every moment. Comedy manipulates expectations; acting
participates in the manipulation.

## Mechanism performance language

Each comic mechanism gets a vocal delivery plus puppet performance,
decided per take as reinforce / conceal / contradict (breaking the
default can be funnier; the director decides knowingly):

Incongruity/misdirection: establish normality, then pivot — neutral
pose before sudden expressive change. Rigidity: utter sincerity
despite absurdity — continue the habitual gesture while everything
goes wrong. Status reversal: confidence collapses, voice tightens —
neck retracts, body contracts, gaze lowers. Taboo: confessional,
conspiratorial, or shamelessly casual — lean to mic, glance at
audience. Deadpan: flat, restrained — near-perfect stillness.
Escalation: urgency/pitch/pace rising — signature pose repeated with
growing intensity. Callback: familiar rhythm, slight emphasis —
repeat the recognizable gesture. Dramatic irony: oblivious sincerity —
audience-facing camera holds the confident expression. Self-deception:
defensive certainty — gesture contradicts the claim.

## Three takes, one JokeBlock (Gerald meditation example)

Same construction (non-attachment collides with obsession), three
deliveries: generic-AI-announcer (telegraphs the punch, flattens
contrast), deadpan self-deception (sincere voice, 350ms pause, slight
neck rise, 900ms dead hold — audience sees what Gerald misses),
accidental confession (smug authority decaying into hesitation and
slow neck withdrawal — the performance adds a second joke). The system
learns which interpretation + delivery works per character, not just
which joke is funnier.

## JokeBlock performance intentions (schema)

JokeBlocks carry `comic_intent` (audience_expectation,
character_belief, reveal, audience_should_notice) plus
`delivery_strategy` (style e.g. oblivious_sincerity, conceal_punchline,
voice energy/pace/emphasis, acting list). Intent states the effect;
the performance plan is one way of achieving it — same block, many
takes, no rewrite. See `comedy/theory/mined/` for the mechanism
vocabulary this draws on.

## PogCritic: four passes, in order

1. Blind viewing (video only): what is the character communicating,
where does interpretation change, what reads as punchline, apparent
sincerity vs sarcasm, distractions, momentum loss, intentional vs
render-delay pauses — all timestamped. Measures what the performance
communicates, not what creators claim.
2. Intention reveal: compare observed vs JokeBlock intent in a table
(sarcastic TTS vs unaware hypocrisy → irony overdose; telegraphed
gesture vs surprise → anticipation spoils reversal; smug-throughout
vs embarrassment → missing transition; random callback → weak setup).
3. Technical verification: deterministic checks on every critic claim
(audio activity vs mouth states, measured pause durations, camera vs
geometry). SyncNet-style alignment is an auxiliary test where facial
geometry suits it — never a universal aesthetic metric, never valid
for replacement mouths without validation.
4. Take comparison: pairwise (surprise preservation, delivery
believability, readability, rhythm, intent strength, naturalness)
with exact reasons — never lone scores out of ten.

Tooling: agentic video understanding (Gemini-class, timeline
navigation, high-rate moments of interest — 1fps sampling misses
mouths), Qwen3-Omni-class alternative, FFmpeg + forced alignment +
acoustic analysis, PogMotion telemetry, critic-ordered close-ups of
failure moments. Output: PerformanceReport (timestamped observations,
technical failures, interpretations, uncertainty, candidate
revisions) → A/B takes + human feedback → character delivery
learning. Critic judgments are hypotheses; audience testing decides.

## Timing analyzer (voice as first-class signal)

Waveform + forced alignment + prosody per JokeBlock performance:
speech rate, pitch/intensity contours, pre-punch pause, post-punch
hold, hesitations, gaze target, motion density, reaction timing —
judged against the intended style (deadpan vs manic ideals differ).
Implemented: `scripts/timing_profile.py` (energy contour, pause
inventory, rate, pre/post-punch holds from plan + audio).

## Audience knowledge model (foundational)

Track three perspectives explicitly: Character (what Gerald
believes), Audience (what viewers likely infer), Director (what to
reveal/conceal). Fabricated-story example: Gerald believes he's
impressive, audience suspects lying, director knows Buzz has proof —
so the director plans the reveal or holds on Gerald as Buzz enters.
A sideways glance establishes knowledge with no joke required.

## First experiment (protocol, not yet run)

One character, one 20–30s block, fixed GLB/stage, four deliveries
(deadpan, confessional, overconfident, nervous): blind interpretation
vs intent, timestamped defects, one revision per take, re-render,
blind human A/B. Dataset keeps takes, criticism, revisions,
preferences. Do not build a critic swarm first.
