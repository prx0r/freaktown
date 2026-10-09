# Comedy theory (reading shelf)

Two foundational texts, imported 2026-10-08 from the `stallshark`
bucket into `r2://freak-town/comedy-theory/`. Pointers live here in
`manifest.json`; bytes live in R2 plus the gitignored local cache at
`data/comedy-theory/`. Fetch with:

```bash
python3 scripts/fetch_r2_media.py --theory   # Freud + Attardo PDFs
python3 scripts/fetch_r2_media.py --papers   # 6 research papers
```

## The shelf

- **Bergson — Laughter: An Essay on the Meaning of the Comic**
  (`bergson-laughter-4352-h.htm`, committed here — public domain
  Gutenberg ebook 4352, mirrored to R2 as backup). Mechanical
  inelasticity, comic of character/situation/words, snowball
  cause-and-effect, repetition and inversion, interference of
  series. Read the snowball and series-interference chapters as
  escalation grammar for `corpus.py` mechanisms, and the
  character chapter as vocabulary for performer `expression` beats.
- **Freud — Jokes and Their Relation to the Unconscious** (Strachey
  translation). Condensation, displacement, indirect representation,
  economy of psychic expenditure, tendentious vs innocent jokes.
  Read it as mechanism vocabulary: Freud's "techniques" map cleanly
  onto what `comedy/corpus.py` calls mechanisms.
- **Attardo — The Linguistics of Humor: An Introduction.** Script
  opposition, logical mechanisms, GTVH, joke structure and punchline
  placement. This is the closest thing to a spec for
  `comedy/rhythms.py` archetypes and `comedy/director.py` beat
  classification — read the rhythm set against GTVH knowledge
  resources before adding a sixth archetype.

## How to use (and how not to)

- **Do** mine these for timing/structural grammar: setup → turn →
  punch → tag, pause placement, callback distance. That is what the
  comedy compiler eats.
- **Do not** ingest copyrighted text into the corpus as source
  material. `corpus.analyze()` is anonymous by design (structure +
  source hash, never source text) — keep it that way. Theory informs
  the grammar; it never ships verbatim in a set.
- **Do not** commit the PDFs to git or redistribute them. R2 +
  local cache only.

## Growing the shelf

Add future resources the same way: original stays where it is,
server-side copy into `freak-town/comedy-theory/`, pointer entry in
`manifest.json` (r2 key, size, etag, author, themes), one paragraph
above saying what it teaches the compiler.

## Research papers (`papers.json` + `data/comedy-theory/papers/`)

Six papers shelved as PDFs, mirrored to `r2://freak-town/comedy-theory/papers/`
— the-numbers-behind-the-design shelf:

- **Multi-Agent Comedy Club** (Hong et al., arXiv:2602.14770) — social
  memory wins 75.6%. Characters must remember reception, not scripts.
- **RAGthoven** (Suppa et al., arXiv:2607.13189, CC BY-SA) — Planner to
  Writer to Reflector to Judge over a 98-joke corpus; simplicity beats
  sprawl. Working repo in `data/github/ragthoven/`.
- **HumorRank** (Ajayi & Mitra, arXiv:2604.19786) — GTVH pairwise
  judging plus Bradley-Terry. Mechanism mastery beats scale.
- **HumorBench** (Narad et al., arXiv:2507.21476) — ~300 pairs with
  objective element rubrics. Paper only; source cartoons stay with
  their owners.
- **Multimodal humor survey** (Liang et al., arXiv:2607.19011, CC BY) —
  visual contradiction needs its own representation.
- **Play-mirth theory** (Frontiers 2024, open access) — motive-consistency
  decides whether a line lands or offends.

Metadata-only (no lawful open copy found, consult via library): Masek &
Prakken's **Playful Transgression Theory** (2025), Vorhaus's **Comic
Toolbox**, Kaplan's **Hidden Tools**, the **UCB manual**. Never pirate
books into this folder — bibliographic entries only.

## Mined gold (`mined/` — structured, JokeBlock-ready)

Every PDF/HTML on this shelf has been read and reduced to working
parts, 2026-10-08. Shapes mirror figgsite templates and the v2 engine
registry; staged for merge, not yet merged:

- `operators-v2.json` — 9 new operators (Bergson snowball, interference,
  repetition, inversion, register-transpose; Freud condensation,
  double-meaning, displacement, opposite, repartee, facade, allusion)
  with instruction plus diagnostic, each mapped to extend/refine/pair.
- `gtvh-fields.json` — script opposition, 12 logical mechanisms,
  situation, target, narrative strategy, language as JokeBlock fields.
- `taboo-gates.json` — 7 Freud vetoes plus 4 cross-modal safety gates
  plus the target_stance record.
- `judge-protocol.json` — HumorRank closed vocab (8 mechanisms, 6
  delivery features, 6 failure modes), duel procedure, Adaptive Swiss
  plus Bradley-Terry selection, cross-judge stability practice.
- `critic-rubrics.json` — HumorBench element schema, autograder pattern,
  worked giraffe-podcast examples.
- `social-memory.json` — MACC reception/social-memory schemas plus loop
  params, RAGthoven 4 stages, 98-joke corpus spec, 16 mechanisms, the
  anti-sprawl constraint.
- `scene-pregate.json` — play-mirth playful-turn plus
  motive-consistency pre-gate with thresholds and reframe/drop routing.
- `delivery-extensions.json` — 8 proposed delivery.v2 fields (visual
  contradiction, face holds, grounding refs). Frozen v1 untouched.
- `premise-territories.json` — 9 reusable situation seeds.
