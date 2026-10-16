# Context compilation — one LLM, many sealed minds (no per-character LoRA)

Saved 2026-10-08. No LoRA per comedian — not initially, maybe never
per character. One strong general LLM, separate private contexts,
structured memory, multiple takes. (Shared comedy-structure LoRA
later only; individual LoRAs only for proven mature voices; RL/DPO
only with substantial human comparisons. Precedent is suggestive,
not licensing: OpenMic's fine-tuned joke writer doesn't imply one
adapter per comedian.)

## The gap that generates comedy

A character who knows he's a narcissist making narcissist jokes is a
routine. A character who sincerely believes he's unusually humble
while constantly revealing narcissism is an engine. Unrecognized
traits (exhibited, not recognized — Nolan's ego) and unobserved
traits (private knowledge — Nolan's secret therapy-dog dream) both
work, but differently. Implementation rule: never hand the character
model the external diagnostic label. The director builds environments
and observations from which the behavior emerges; the character may
hold a distorted first-person belief about the trait instead.

## Subjective simulation, not roleplay

No "be Nolan, be funny." Nolan gets a life: sensory observations,
belief formation, goals, memory, decisions; speech arises from
decisions. World state → perception filter (noticed/missed/
misunderstood) → private beliefs and motivations → decision (defend,
investigate, impress, conceal) → speech/action in own voice → world
consequences, memory updates. Director arranges comic situations
without dictating speech. Nolan explaining his competence IS the joke;
his terrible evidence vs his triumphant interpretation is rigidity
plus dramatic irony as a reasoning process.

## Blindspot Engine (schema)

Every Pog gets three director-assigned traits plus a reflex:

- conscious_desire (both know — Nolan wants the commissionership)
- hidden_drive (director only, leaks into choices — terror of being
  ordinary)
- false_self_belief (character believes, director knows false — never
  needs validation)
- behavioral_reflex (unstated bias on action selection — challenged
  competence → bolder claims)

Plus perception_rules (success→own skill, failure→external
interference). Weights are starting values, not learned parameters.
Implemented: `assets/character-meshes/cast/blindspot-schema.json`,
instance `blindspot-sergeant-sled.json`, template for the cast.
Access control, not prompt instruction: the character call must never
contain the secret — told-to-ignore is not separation.

## Research grounding (test, don't assume)

False-belief consistency is an open problem (ToMATO-style asymmetric
information benchmarks; documented gaps between stated beliefs and
behavior). So tests ask: confronted with unfamiliar situations, does
Nolan decide from his worldview, surprise without dissolving — not
"does the description sound distinctive." Memory-driven roleplay
evidence supports structured retrieval before adapters. Stand-up
needs intentional craft AND accidental comedy: Nolan prepares bits
(intention) while his work stories detonate (sincerity) — then his
wrong theory of his own appeal (they love my techniques!) drives him
to write worse-better material. The learning process itself becomes
the comedy, with dramatic irony between comedian, audience, director.

## Instantiation pipeline (per request, no training)

Agent prompt → character compiler (subjective beliefs, hidden flaws,
goals, memories) → director mines 10–20 premises (theory, world
truth, blind spots) → character writes from subjective experience
(no flaw labels, no global analysis) → set editor arranges →
PogMotion performs, critic reviews → audience feedback updates
policy. Writing room internals: subjective autobiographical memory
(Heathrow: unconventional technique vs cupboard), personal humor
theory (allowed to be wrong — the distortion is the material),
writing ops (find_angle, heighten, make_specific, write_tag,
add_callback, test_delivery) grounded in subjective info only.
Minimal agent interface: one `create_performance` call (character,
topic, duration, world, mode) → job ID → playable URL + transcript +
profile; later calls reuse identity and history. Proof experiment:
same Nolan in three architectures (generic prompt / subjective /
subjective + hidden director), five sets each, blind judging on
distinctiveness, consistency, surprise, humor — with recognition
(without being told the speaker) as the durability metric.
