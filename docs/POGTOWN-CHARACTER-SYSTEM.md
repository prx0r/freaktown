# Pogtown character-comedy system — full documentation

Status: design record + build map, 2026-10-08. Read alongside
`docs/POGTOWN-ENGINE.md` (figgsite↔freaktown contract),
`docs/POGTOWN-ROSTER.md` (cast), `docs/POGTOWN-SPLATS.md` (stages),
and `comedy/theory/` (the reading shelf). Game truth lives
pogtown-side; freaktown consumes through adapters, never reimplements.

## 1. The bet

Pogtown is a persistent universe of characters with personalities,
relationships, memories, comic instincts, and reusable physical puppet
bodies. Characters develop histories, rivalries, reputations, and
distinctive ways of interpreting events. They do stand-up, podcasts,
poker, interviews, and scenes with human-owned Pogs.

The founding distinction, and the one everything below hangs on:

> Biology supplies the possibilities. Psychology supplies the comedy.
> Relationships supply the longevity.

A giraffe that talks is a novelty with ten jokes in it. A giraffe with
an inflated sense of his own attractiveness, a history of terrible
romantic decisions, a mosquito who knows too much, and a lioness ex who
has heard it all before — that is a renewable comedy source. Anatomy is
an affordance; psychology is the engine; relationships are the memory
that makes episode 40 funnier than episode 1.

A second distinction with architectural force:

> Character identity ≠ comic mechanism ≠ comic material.

A character is persistent. A mechanism (misinterpretation, reversal,
self-deception) is a reusable operation. Material is the utterance or
performance produced on a given night. Store the three separately so
one character can use many mechanisms and one mechanism can serve many
characters. Whenever two of these collapse into one field, the system
loses either identity stability or generative range.

## 2. The four levels (what we are building toward)

Level 1, novelty — a giraffe that talks. Incongruity that evaporates
once accepted. Level 2, stereotype — a giraffe with human habits. One
dimension, wider but shallow. Level 3, psychological contradiction — a
giraffe with a private life: self-described romantic, actual shameless
opportunist, desperate for approval, blind to rejection. Now he can do
sex, religion, politics, death. Level 4, social and dramatic
contradiction — a giraffe with a reputation. The lioness knows. The
mosquito has receipts. His therapist, an owl, is losing patience. Every
interaction activates a different comic possibility, and his mere
arrival changes what the audience expects of others.

Pogtown characters must be authored at level 3 and deployed at level 4.
Anything below that is a sketch, not a cast member.

The displacement mechanism that makes this work: recognizable human
impulse (vanity, lust, shame, status-seeking) through alien embodiment
(neck, feeding habits, shell, train-station pigeon) applied to an
unexpected social institution (dating, therapy, boardrooms, funerals),
delivered with a distinctive comic perspective — the character
describing the outrageous as perfectly normal. The failure to notice is
funnier than the announcement. Same mechanism covers objects: jealous
traffic cone, devout parking meter. The object supplies something to do;
the psychology supplies what it means.

## 3. The six comedy sources (character authoring checklist)

Every Pog is authored against all six. Embodiment: what is physically
possible or impossible (novelty and physical comedy; never the sole
source). Human drives: vanity, lust, jealousy, shame, ambition,
boredom, revenge (this is what lets one character enter any situation).
Self-deception: what the character believes that is clearly untrue
(reusable dramatic irony; the audience knows). Social relations: who
knows them, loves or despises them, has leverage (variations the
character cannot generate alone). Institutions: interviews,
interrogations, funerals, podcasts, retreats (fresh norms to
misunderstand or violate). History: bans, grudges, callbacks, things
being concealed (this is what turns sketches into a universe).

Each character additionally carries a transgression grammar: the normal
expectation attached to them, and their recurring transgression of it.
Giraffe, gentle herbivore → sleazy self-important romantic. Mosquito,
irritating insect → connoisseur of intimacy. Snail, slow and harmless
→ violently impatient productivity obsessive. Pigeon, common street
bird → aristocratic bloodline snob. Goldfish, forgetful → paranoid
archivist. Traffic cone, inert equipment → authoritarian bureaucrat.
One primary worldview must explain how a character's several independent
contradictions fit together, or the character dissolves into random
traits — and the contradictions must interact, so that need causes
bragging, vanity prevents retreat, and physique makes the secrecy claim
ridiculous. Interaction of contradictions generates situations, not gag
lists.

## 4. System architecture (as built, as proposed)

Four pieces, agreed: CharacterGraph (identity, personality,
motivations, relationships, memories), JokeBlocks (premises, mechanisms,
punchlines, callbacks, delivery), Director plus gates (select,
generate, evaluate, escalate, stage, perform), Performance Runtime (GLB
actors, puppet animation, voice, staging, audience reactions).
Marble splats supply reusable stages — store, podcast room, interview
studio, red carpet, poker hall. Stages are not the product; portable
characters, the social graph, the comedy system, and the authoritative
event runtime are.

What exists today, verified on this box. The v2 character engine
(`pogtown_character_engine_v2.zip`, 165 files, 5 tests green) implements
the semantic layer: CharacterGraph with core, expression, dynamic
state, world model, status model, knowledge boundary, perception,
action policy, comedy priors, relationships; CharacterBlockView as the
junction object of one mind seeing one world; PremiseCandidate with
operator trace and grounding claim IDs; GateResult with hard vetoes for
false grounding, swappable-character genericity, and missing operator
trace; dual memory keeping objective claims separate from subjective
interpretation; relevance-gated wakeups so most characters ignore most
blocks; deterministic bootstrap mining that runs with no LLM. Figgsite
holds the content layer: 27 JokeBlocks under `templates/blocks/`, 15
theories in `templates/theories.json`, 12 world operators as pure
functions, a classifier, a judge with dimensions and vetoes, premise
packs (84 premises across six packs), four `pogtown.character.v1`
character files, a 17-entry public-domain cast registry with
jurisdiction gates, and evergreen trees for event activation.
Freaktown holds the performance layer: the `comedy/` compiler
(corpus → rhythms → director → delivery.v1 → evaluator), frozen
`delivery.v1` contracts, the StageRuntime package, intake sealing, and
now the theory shelf. The pogtown-mvp checkout holds the runtime
doctrine: Freak as portable entity, game as portable rules pack,
event-sourced performance actions, renderers as renderers.

What is genuinely missing, in build order. First, the interaction
model: v2's work room runs characters independently, so incompatible
goals never collide in code — the Dramatic State Engine (shared
situation state, per-character policies, contradiction detector, state
updates between turns) is the next invention and needs no new schemas.
Second, the premise-to-delivery adapter: the comedy director takes
written lines, not PremiseCandidates, so accepted premises have no
path to the stage. Third, asset QA: the roster names starting GLBs
(Quaternius CC0 frog, cats, robots; Meshy and Poly Pizza listings)
that have never been technically inspected — the staged meshes in
`assets/character-meshes/` are first in that queue. Fourth, the
audience learning loop that separates joke exhaustion from character
popularity.

The target loop, stated as an invariant: character state plus world
event → candidate JokeBlocks → comic gate plus character-consistency
gate → director compiles timed puppet performance → audience feedback
plus persistent state update. Every performance informs the next
without letting scores overwrite identity.

## 5. JokeBlock ontology (frozen v1 + the proposed extension)

Figgsite's frozen v1 fields: id, parent, tags, sources, facts with
claim status (the engine may play with comic-model claims, never assert
unconfirmed ones), culture (analogues, frames, meme objects, staleness,
audience camps, heat), comic claim, reality model, comic model,
theories with strengths, tensions, characters, premise IDs,
derivations, references, minted, results. The canonical upgrade adds
identity, central question, confirmed/unknown/false reality split,
timeline, quote bank, actors, theory handles, premise and derivation
territories, open questions, changelog.

The proposed extension from the October research — and the one to
adopt — describes each block as a reusable comedic transformation with
mechanism, setup, expectation, violation, target, escalation,
punchline, delivery, callback hooks, and performance history. The
CharacterGraph decides who would make the joke; the block decides why
it could be funny; the Director handles timing, reversal, and scene.
Store mechanisms and expandable premises, not punchlines: a mosquito
lifelong-blood-donor premise is worth more than any single joke written
from it, because each answer (the bank, the charity gala, the loyalty
card) breeds further premises. Premise density beats joke density.

## 6. Character profile format

Figgsite's `pogtown.character.v1`: id, name, archetype, traits, mask,
voice cadence and tells, humour, preferred theories, block affinity,
memories, callbacks, sets, status (candidate/returning/regular),
dramatic core (want, fear, need, dominant humour, self-model, blind
spots), status model, knowledge (native period, knows, does-not-know),
perception (notices first, ignores), action policy, comedy operator
priors, relationships, threads. The roster adds the acquisition path:
identity plus provenance → performance GLB → voice package → graph →
JokeBlock adapter → runtime, all under one `pog.*` actor ID across
stage, news, games, and merch. Voice rule, repeated because it matters:
never bake personality entirely into audio — rhythm, habits, triggers,
and dialogue style live in the graph so TTS providers stay swappable.

## 7. Supporting theories (the shelf and what each one is for)

Classics in `comedy/theory/`: Bergson's Laughter (public domain,
committed in-tree) for rigidity, snowball escalation, and series
interference as escalation grammar; Freud's Jokes (Strachey) for
condensation, displacement, tendentious vs innocent jokes, and the
taboo dimension; Attardo's Linguistics of Humor for script opposition
and logical mechanisms as explicit block fields. Papers in
`comedy/theory/papers.json` with PDFs mirrored to R2: Multi-Agent
Comedy Club (social memory conditions generation, 75.6% preference —
remember reception, not scripts); RAGthoven (Planner→Writer→Reflector→Judge
over a 98-joke corpus; simple pipelines beat writers-room sprawl; repo
cloned to `data/github/ragthoven/`); HumorRank (GTVH pairwise judging,
Bradley-Terry aggregation, mechanism mastery beats scale — the
head-to-head comparison method per character); HumorBench (~300 pairs,
objective element rubrics — the critic explains mechanisms, never just
scores; source cartoons stay with their owners); the multimodal survey
(visual contradiction needs independent representation — faces, timing,
staging are not text-to-speech); play-mirth theory (motive-consistency
decides whether a line lands or offends — scene framing is load-bearing).
Metadata-only, consult via library, never pirate in: Masek &
Prakken's transgression theory (one grammar per character), Vorhaus
(premise, opposites, character engine), Kaplan (objectives and
adversity), the UCB manual (finding and heightening the game).

## 8. Datasets, repos, and the license line

Useful and held: RAGthoven's 98-joke mechanism corpus and ten
experiment configs (`data/github/ragthoven/`); MUStARD code and
sarcasm annotations (`data/github/mustard/`, MIT — video stays
upstream); Humicroedit and HaHackathon as scorer-calibration references
(benchmarks, not training assets, offence modelled separately from
humour). Sitcom transcript corpora (Friends, Big Bang) are research
benchmarks where permitted, never distribution assets — copyrighted
scripts do not enter Pogtown's training or shipped data. Same rule
covers HumorBench source images and any Dogpile of "public GitHub"
media: public access is not a commercial licence. The dataset Pogtown
itself must build is the missing one: Character–Situation–Mechanism–Reaction
records keeping causal structure (private motivation, contradiction,
mechanism, audience knowledge, result, callback, ratings, timing,
relationship deltas) so the system can learn which characters are
funnier humiliated, which mechanisms suit which relationships, and how
taboo lands as familiarity grows.

## 9. The pilot experiment

Three characters (giraffe, mosquito, judgmental pigeon), three
representation levels (species only; psychology plus species; full
dramatic character with history, relationships, and audience
knowledge), one situation (dating podcast with the ex and the mosquito
as surprise guests), same topics, same budget, same selection. Human
judges compare performed clips — not scripts — on immediate funniness,
voice distinctiveness, predictability, desire to see more, and
character-specificity. Then a second episode with returning viewers,
because the metric is not the funniest line but the character people
want to spend time with. Twenty candidate scenes per condition down to
a balanced performed set, blind comparison. A proposal, not yet a
protocol.

## 10. Project boundaries (do not blur these)

Pogtown: persistent character universe, games, conversations,
performances. FunnyLab: comedy generation, classification, evaluation
experiments. JokeBlocks: portable comic structure and material.
Pogpet: shared character creation and asset pipeline. Freaktown: one
show format inside the ecosystem — product, stage, performance
contracts, delivery, Ella, the live site. Figgsite mines what is
funny; freaktown learns how to perform it. Game truth lives pogtown-side
and is consumed through adapters. The archive is read-only.

## 11. Asset inventory (this box, 2026-10-08)

Theory: `comedy/theory/` (manifests, Bergson in-tree, papers.json) →
bytes in `r2://freak-town/comedy-theory/` → cache in
`data/comedy-theory/` → fetch via `scripts/fetch_r2_media.py`. Meshes:
`assets/character-meshes/manifest.json` → 13 staged GLBs in
`r2://freak-town/character-meshes/` → cache in
`data/character-meshes/`. Engine: v2 zip at
`/tmp/opencode/pogtown_character_engine_v2.zip`. Content: figgsite
`templates/` (blocks, characters, premises, theories, evergreens, PD
cast) and `backend/creative/`. Runtime doctrine: pogtown-mvp `docs/`
and `games/` (mafia, pictionary, poker, roast-relay, standup). Packs:
`pogtown/comedy-packs/` (halloween/xmas comic sidecars with premise
families, mechanisms, panels). Face/vocabulary layer: freaktown
`face_profiles.py`, `contracts/`, `comedy/`.
