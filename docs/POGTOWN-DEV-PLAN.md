# Pogtown Development Plan — canonical puppet comedy universe

Saved 2026-10-08 from the owner's directive. Sequencing amendment:
**Blender first, Marble later.** The spatial pipeline (Phase A) is
deferred; all performance work renders through Blender offline until a
splat stage is needed. No new monorepo, no new game protocol, no new
joke database until existing pieces are exhausted.

Governing rule: worlds, puppets, comedy material, and performance
state stay separable, persistent, and recombinable. Every improvement
in world models, voice, animation, or LLMs must make existing
characters and their histories more valuable — never require rebuilding
them. Freak Pack (`freak.pack.v1`) and `pog.events.v1` stay compatible.

## Product

A persistent, explorable comedy universe: AI characters inhabit
generated physical environments, develop material, perform it, and
evolve through interaction. Central experience: generate a club, load
a Pogpet GLB, give it personality/relationships/JokeBlocks, let it
rehearse through the comedy engine, watch it perform with voice,
expression, timing, cameras, and reactions, intervene as director,
preserve the show, learn, export clips.

Two modes from day one, same canonical identities and JokeBlocks:
**Rehearsal** (async, cheap: generate, listen, critique, revise) and
**Live** (continuous performance, interruptions, improv, recall).

## Reuse map

| Repo | Owns | New role |
|---|---|---|
| Pogtown | Rooms, Freak Packs, stand-up events, reactions, replay, director cuts, clip metadata | Spatial performance runtime |
| Freaktown | Comedians, set delivery, host/Ella, TTS show flow | Principal comedy-writing + performance-control service |
| Pogpet | Character assets, GLB pipeline, voice/video infra | Canonical puppet bodies and rigs |
| New spatial pkg | — | Marble jobs, Spark renderer, anchors, GLB composition (LATER) |
| Comedy mining | Set foundations exist | Theory-grounded premise search, rehearsal, evaluation, memory |

## Architecture

Studio/Live World (web UI, Three.js, splats later, GLTFLoader) →
Spatial Runtime (worlds, anchors, cameras) → Performance Director
(dialogue, pauses, gestures, reactions, interruptions) → Comedy Engine
(CharacterGraph, JokeBlocks, premises, mechanisms, critic, rehearsal)
→ Pog Runtime (identity, authorized actions, room state, append-only
events, replay) → Media services (Marble API later, GLBs, TTS,
FFmpeg, R2, Postgres) → Authenticated MCP server (agent creates
worlds, casts, mines, starts shows, retrieves clips).

Renderer decision: **Blender offline now**, Three.js + Spark when the
splat stage lands, Unreal optional ever. Provider independence:
scenery suppliers never control characters, dialogue, or game state.

## Comedy intelligence (the differentiator)

Four stores, never flattened into one prompt: CharacterGraph (who),
JokeGraph (why material works), SituationGraph (what happens),
PerformanceGraph (what actually happened). Start as Postgres + JSONB;
no graph DB yet. Operators: script collision, rigidity,
self-deception, status reversal, taboo displacement, escalation,
inversion, callback, literalization, relationship conflict — theories
generate candidates, never guarantees. Pipeline order: premise
discovery → joke development → performance construction. JokeBlocks
versioned, never destructively rewritten; predicted laughs never stored
as observed laughs. Three evaluation layers: structural critic,
comparative critic (pairwise, not scalar), human evidence. Exhaustion
model at four levels (exact joke, premise, mechanism, cliché);
repetition vs callback = whether recurrence adds meaning.

## Performance

Set compiler (60s shape: entrance, opener, premise, escalate, payoff,
callback tag; measure TTS, don't estimate) → versioned SetPlan over
immutable JokeBlock revisions → one-clock timeline (audio, motion,
captions, reactions, cameras). Mode A sealed performance first
(reproducible, testable); Mode B live improv on top. State machine:
IDLE → PREPARING → WALKOUT → PERFORMING → WAITING_FOR_REACTION →
IMPROVISING → CLOSING → COMPLETE, with PAUSED/CANCELLED/FAILED paths.
Director vs Ella vs Comedian separation holds: host never rewrites
identity or canon.

## Alive engine (later, in order)

Character mind (stable identity vs temporary state; remember
consequential events, not every utterance) → comedy actions
(perform_bit, riff, heckle_back, confess, deflect, challenge, callback,
abandon_bit, invite_guest, react, pause, exit_stage) → live crowdwork
(synthetic audience marked synthetic first) → character-vs-character
scenes with hidden state (goal conflict, not turn-taking) → dual
memory update (objective history vs subjective interpretation; the
mismatch is future material).

## Recording, clips, MCP

Record everything for replay (world/asset/rig/set/audio versions,
timestamps, cues, camera decisions, audience origins, hashes) →
browser-capture now, deterministic offline renderer later (CPU VPS =
control plane only; GPU worker for heavy renders; no permanent GPU
server for first clips) → clip selection on human evidence +
structural completeness, not loudest sim reaction → publish pipeline
ending in authorized approval only. MCP tools: world create/get/
calibrate, character create/cast/get, material mine, jokeblock
develop, set compile, show rehearse/start/observe/direct, clip
render/publish — typed I/O, long jobs with polling, idempotent
retries, runtime commits authoritative state only.

## Boundaries

Character mesh/body: Pogpet. Comic psychology: Freaktown (by
character ID). JokeBlocks/sets: Freaktown. Worlds/calibration:
Pogtown. Performance/game events: Pogtown. Media: R2. Audience
evidence: Pogtown records. Publishing: auth store. Replay pins
resolved snapshot IDs so later edits can't rewrite old shows.

## Milestones (demos, not code-complete claims)

M0 integration audit (contracts run, one real GLB inspected, reusable
modules mapped). M1 one stage + one real GLB, controllable camera.
M2 60s intelligible speech with synced gestures. M3 mining operational:
three distinct character-grounded sets with provenance. M4 live
directed show with interruption + memory use + clean resume. M5
reproducible captioned vertical clip + authorized draft post. M6
two-character scene with competing goals and real responses.

## Budgets

One generated venue until renderer + positioning work; canonical
worlds stored permanently, never per-performance Marble calls (and no
Marble calls at all until Blender path works). Cache voice per
text/voice/model revision. Batch comedy generation offline. Repeatable
everything: immutable assets, deterministic timeline, versioned models.

## Autonomy levels (in order)

L1 autonomous preparation (mine, write, rehearse unwatched). L2
autonomous performance (timing, reactions, callbacks; director keeps
authority). L3 autonomous social existence (relationships, goals,
games) — only when L1+L2 cohere. Gerald wants fame because he needs
admiration; theory becomes agent architecture.

## Sprint 1 (current)

Blender-first living puppet: repo tests + contract check → one real
GLB inspected → TTS to performer → idle/speech/pause/emphasis motions
→ existing Pogtown timeline drives render → one reproducible 60s set.
Excluded: accounts, multiplayer, casinos, Unreal, animation
generation, commerce, graph DB. Then Sprint 2 (CharacterGraph/JokeBlock
rehearsal selection), Sprint 3 (interruptions, audience, memory),
Sprint 4 (clips, distribution, MCP).
