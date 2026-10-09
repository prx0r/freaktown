# Comedian learning — distinct voices, not one optimum

Saved 2026-10-08. Every Pog is an individual comedian developing its
voice through experimentation. One shared LLM reading one news feed
for one laughter signal converges on one style. Differentiation must
be in the learning system, not just the prompts.

## Attention policies, not voice skins

Same event, three readings: Gerald (sexual vanity) sees alien romance;
Buzz (parasite entrepreneur) sees customers or leads; Percival (class
obsession) sees unregulated immigration. Pipeline: event →
character-specific attention → emotional reaction → private
interpretation → mechanism → JokeBlock. Never: event → generic jokes
→ rewrite in voice. That second pipeline is the convergence machine.

## Reward collapse and the quality-diversity answer

One laughter optimum homogenizes the cast (cf. MAP-Elites literature:
many distinct high performers, not one peak). Don't optimize the
single funniest comedian; curate a population funny in distinct ways.
Per-character competence zones plus scheduled excursions (Gerald does
economics through romantic insecurity; failures allowed, discoveries
expand repertoire).

## Three layers per comedian

Immutable-ish identity (worldview, flaws, history, motivations) →
learnable policy (topics, mechanisms, delivery, risk, callbacks) →
personal repertoire (hits, bombs, work-in-progress, room-specific
sets). Identity constrains search; policy learns inside it. Discovery
beyond the brief is the goal (Gerald's deadpan rationalizations
outperforming his bragging), but identity never dissolves.

## Private repertoire + shared JokeGraph

Shared news/situation feed; per-character candidate sets; global graph
recording premise ownership, semantic similarity, mechanism
diversity, prior performances. Store per JokeBlock: event ref,
perspective, premise, mechanism, punchline + variants, who performed
similar material and how it went. Deduplicate observations, not
topics: same event with genuinely different mechanisms is legal;
deliberate theft arcs are world events, not duplication bugs.

## Reward (experimental, not validated)

R = wL·L + wC·C + wN·N + wI·I − wD·D: real laughter (normalized),
character consistency, novelty vs graph, interest/replay intent,
minus duplication/exhaustion penalty. No neural training on sparse
noisy feedback — per-character contextual bandits over arms like
deadpan confession, status reversal, sexual misdirection, absurd
escalation, self-deception, callback, with an exploration budget.
Critic rehearsal scores are NOT laughter reward; only human
observation counts as L. Implemented: per-character policy JSON with
arms, estimates, update rule (`policy-sergeant-sled.json` beside the
cast specs; pilot evidence row recorded).

## Selection: Q/N/F

S(j,c) = αQ + βN + γF: predicted quality, global novelty, worldview
fit; per-character weights; filters for duplication, continuity
violations, unsupported claims; update on observed feedback only;
exploratory fraction preserved. Individuality at three levels:
character (vanity/insecurity/delusion), artistic (deadpan confessions
discovered), historical (meditation teacher, Buzz feud — the material
only this history could produce). New models can imitate the brief;
without the history they can't be Gerald.

## Writers' room cycle (bounded schedule)

Observe (rank feed by what the character would care about) → angles
(worldview × concerns × history) → premises (mechanisms, dedupe vs
graph) → write (setups, punches, tags, callbacks) → rehearse
(delivery strategies, critic checks communication) → perform (capture
laughs, replays, feedback) → learn (mechanism/topic/structure
estimates with uncertainty) → evolve (keep, retire, explore).
Implemented state: policy JSON + evidence rows; rehearsal loop runs
through existing director/TTS/QA path.
