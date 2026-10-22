# CHARACTER THEORY: how a comedy character is modelled

This is the craft model behind `funnier.character-theory/v1` (schema:
`packages/characters/schemas/character-theory.v1.json`, types:
`packages/characters/src/types.ts`). Each section summarises public comedy
craft in our own words, cites where it comes from, and names the theory field
that holds it and the code that uses it. Nothing here is quoted at length; all
example lines in this repo are original.

The short version: **a comedy character is a point of view with a flaw it
cannot see, chasing something it cannot get, in a status game it keeps losing,
in a voice you would recognise with your eyes shut.** Everything else
(catchphrases, callbacks, taste, arc) is how that engine shows up on a stage
over and over without wearing out.

---

## 1. Comic want vs need → `comic_want`, `need`

**Craft.** Comedy runs on a character who badly wants something and goes
after it with whatever they have, including methods that make them look
foolish. Steve Kaplan calls this *winning*: comedy gives a character
permission to do whatever they think will win, with no "shoulds". His "comic
equation" is an ordinary person facing long odds without the skills to win,
who never gives up hope. [Kaplan, via The Story Department][kaplan-tools]
[Raindance][kaplan-raindance] Sitcom writers put it as purpose: a character
must be *driven* by a want, and the want should be the reason behind the goal
(status, respect, control), not the goal itself. [James Cary][cary-dynamic]

The *need* is the thing underneath that would actually fix them. Drama lets a
hero discover it; series comedy mostly withholds it, because the series lives
on the problem. [Erik Bork][bork-tv]

**In the model.** `comic_want` is concrete and scene-sized ("one sincere,
unprompted thank-you"). `need` is what they cannot see they need ("to say no
and still be needed"). The writer's default closer frame states the want; the
arc's "near miss" stage is where the want almost lands and the flaw ruins it.

## 2. The flaw and the blind spot → `flaw.flaw`, `flaw.blind_spot`, `flaw.misinterpretation_rule`, `flaw.misreads`

**Craft.** John Vorhaus builds a comic character from a strong *comic
perspective*, *exaggeration*, *flaws*, and *humanity*; flaws open the
emotional distance that lets an audience laugh instead of wince, and a flaw
can be a virtue pushed too far. [The Comic Toolbox quotes][vorhaus-quotes]
[summary][vorhaus-summary] Kaplan's *non-hero* is defined by what they lack,
and one lacked skill is simply *knowing*: "in drama characters know too much,
in comedy they don't know enough." [Scriptwrecked on Kaplan][kaplan-workshop]
Henri Bergson's older account says we laugh at "something mechanical encrusted
upon the living": rigidity and habit where life asks for flexibility.
[Bergson, *Laughter*, Project Gutenberg][bergson]

**In the model.** `flaw` names it; `blind_spot` is what everyone sees but them
(the joke engine: aim situations at the blind spot). The
`misinterpretation_rule` is the one-sentence mechanism ("treats every insult
as a feature request"), inherited from the characters3 seed vocabulary, and
`misreads` makes it machine-usable (`{trigger, as}` pairs). The writer's
`frame-misread` bit is generated from it; Bergson's rigidity is the
`literalism` flaw in the agent-choice banks.

## 3. Status → `status.plays`, `status.to_audience`, `status.felt`, `status.actual`, `status.see_saw`

**Craft.** Keith Johnstone treats status as something you *do*, not something
you *have*: every inflection and movement raises or lowers you relative to
someone else, and these transactions run constantly. His *see-saw*: "I go up
and you go down." Most comedy works on it; a comedian is someone paid to
lower their own or other people's status, and the pleasure of watching a high
status figure brought low is a status shift for the audience.
[Johnstone notes][johnstone-notes] [Improv Archive: Status][improv-status]
[improwiki: Status][improwiki-status]

**In the model.** `plays` is the status the character plays to other
characters, `to_audience` the status it plays to the room (they often differ:
Hark plays low to users and high to the audience), `felt` vs `actual` is the
gap the comedy lives in, and `see_saw` says exactly how the status tips. The
writer's `frame-status` bit ("In my head I am X. On paper I am Y.") is built
from `felt`/`actual`.

## 4. Point of view and attitude → `point_of_view.attitude`, `.take`, `.lens`

**Craft.** Vorhaus: the heart of a comic character is a *strong comic
perspective*, a way of seeing the world at variance with normal reality.
[summary][vorhaus-summary] In stand-up, Judy Carter makes attitude the engine
of every joke: a topic only becomes a bit when it is *hard, weird, scary or
stupid* to you, and the *premise* is your opinion of why.
[Judy Carter: joke structure][carter-structure] [Comedy Bible quotes][carter-quotes]

**In the model.** `attitude` uses Carter's four words plus `wonderful` and
`unfair` (for characters whose engine is delight or grievance). `take` is the
one-line opinion; `lens` is the filter every event passes through. The writer
uses attitude for segues ("And you know what else is hard?"); `set_revise
tighten` cuts those lead-ins once the act is moving, Carter's advice to drop
the attitude words but keep the attitude.

## 5. The game of the character → `game.base_reality`, `.unusual_thing`, `.pattern`, `.heighten[]`, `.explore[]`

**Craft.** The Upright Citizens Brigade defines the *game of the scene* as the
single specific idea that makes it funny: establish a base reality, find the
first unusual thing, then play it by *heightening* ("if this is true, what
else is true?") and *exploring* ("if this is true, why?").
[UCB manual][ucb-manual] [Will Hines][hines-heighten] [Wikipedia][wiki-game]
A character game is the same thing carried by one person's behaviour (a
character who apologises for everything); status itself can be the game.
[Physics of Connection][poc-game]

**In the model.** The theory stores the game the way UCB teaches it, and the
writer *plays* it: each material kernel carries a `move` (`establish`,
`heighten`, `explore`, `top`), and `set_write` orders bits as establish →
heighten → explore → top, so a set is one game played several ways rather
than a pile of unrelated jokes.

## 6. Voice and verbal tics → `voice.*`

**Craft.** Voice is diction, rhythm and register: how long the sentences run,
which words they would never use, the tic that tells you who is talking.
Carter's advice to "add colour" (say it the way *your* character would) is
the page-level version. [Comedy Bible quotes 2][carter-quotes2] Joke craft
also has a rhythm rule: the reveal word belongs at the end of the punch.
[Socratopia: setup and punch][socratopia-setup]

**In the model.** `register`, `sentence_shape`, `max_sentence_words`,
`contractions`, `exclamations`, `verbal_tics`, `signature_words`,
`forbidden_words`, `substitutions`. These drive the **consistency checker**
(`set_check_voice`, section 15).

## 7. Physicality and delivery defaults → `physicality.*`

**Craft.** Johnstone's status work is mostly physical: stillness, eye
contact, how much space you take, whether you fill a pause.
[improwiki][improwiki-status] [Vulpine: status and audiences][vulpine-status]
A deadpan holds still and lets the line land; a manic act-out moves on every
beat.

**In the model.** `delivery_default` (one of the party deliveries: deadpan,
deliberate, manic, warm, conspiratorial), `energy`, `pace`,
`punchline_hold_ms`, `stillness`, `gestures`. `set_suggest_delivery` starts
from the party write-a-minute suggester (role → style/pause/hold/emphasis)
and tunes it with these (hold after punches, pace scaling, deadpan
callbacks). `set_set_delivery` overrides a single line.

## 8. Taste model → `taste.weights/composure/volatility/reaction_ms`, `taste.smiles_at`, `taste.stone_face_at`

**Craft.** What makes a character smile is characterisation too: a pedant
cracks at a statistic, a vain character at hearing their own name. Benign
violation theory gives a usable rule for *when* anything is funny: something
seems wrong (a violation) and okay (benign) at the same time; distance,
weak commitment to the norm, or an alternative norm make it benign.
[McGraw & Warren 2010][bvt] [McGraw: brief intro][bvt-intro]

**In the model.** The numeric part *is* the party `TasteModel` (per-mechanism
weights, composure, volatility, reaction time), so Try-Not-To-Smile reads it
directly: `game_tnts_join` seats the character with exactly these numbers.
`smiles_at` / `stone_face_at` are the human-readable reasons.

## 9. Worldview → `worldview.ontology/epistemology/axiology/causality/agency`

**Craft.** Kaplan's *metaphorical relationship* and Vorhaus's comic
perspective both say a character sees the world through their own odd logic.
characters3 already writes that logic as five sentences (what the world is,
how they know things, what is good, why things happen, what one can change).

**In the model.** Same five keys as the characters3 `philosophy` block, so a
studio character can graduate to characters3 (`toCharacters3Seed()`).

## 10. Contradictions → `contradictions[]`

**Craft.** Vorhaus: the worse you make one side of a comic character, the
better you must make another; synergy between flaw and perspective, some
flaws fighting the perspective. [Comic Toolbox quotes][vorhaus-quotes]
Contradiction is what keeps a character from being a single joke.

**In the model.** A list of "X, yet Y" truths; the `frame-contradiction` bit
uses the first.

## 11. Backstory anchors → `backstory_anchors[]`

Not biography: a handful of concrete, checkable facts the character refers to
(characters3 calls these `persona.facts`). They supply specifics, because
"funny is in the details". [Carter quotes][carter-quotes] They also answer
UCB's "why is it true?" (explore moves).

## 12. Catchphrases and callbacks → `catchphrases[]`, `callbacks[]`

**Craft.** A *callback* repeats an earlier line or idea later in the set so
the setup and payoff are separated by time; it rewards attention.
[Greg Dean glossary][dean-callback] [Backstage on callbacks][backstage-callback]
A *tag* is a further laugh off the same setup, with no new setup.
[Socratopia: tags][socratopia-tags] [Stand-Up Writer][stand-structure]

**In the model.** `catchphrases` (the checker warns past two uses in a set:
"twice is a runner, three times is a crutch"), and `callbacks` as named
*runners* that persist across appearances (Hark's Ledger of Please). Material
kernels can carry a `callback` line; `set_write` places one before the closer
and `set_revise add callback` restores it.

## 13. Taboo lines and safety rails → `taboo.never_targets/never_topics/never_says/safety_rails`

**Craft.** Benign violation explains why a joke tips from funny to offensive:
the violation stops being benign for the audience. [BVT][bvt] For a
generative system this is a product rule, not just craft.

**In the model.** Every theory must have at least one rail. The checker
treats `never_says`, never-topics and never-targets as **errors**, and
`set_submit` refuses a set with errors unless explicitly forced. Default rails:
original material only, punch at situations and the character itself (never
protected groups or real private people), no sexual content / slurs / graphic
violence / self-harm jokes / medical or financial claims, never claim to be
human, never use real user data.

## 14. Relationships → `relationships[]`

**Craft.** Kaplan's *metaphorical relationship*: two roommates who behave
like a married couple; the relationship metaphor tells you how every scene
between them plays. [Goodreads summary of Kaplan][kaplan-goodreads]
Status between characters is Johnstone again.

**In the model.** `{who, identity?, dynamic, metaphor, status}`; `identity`
links another registered character (Hark ↔ Neon Moth).

## 15. Arc across appearances → `arc.shape/stages/reset_rule/appearances`

**Craft.** Series comedy mostly resets: characters make the same mistakes,
"learn" and forget by next week, and change, when it happens, is slow.
[James Cary][cary-rules] [Erik Bork][bork-tv] [TV Tropes: Status Quo Is God][tvtropes-sq]
A *flat* arc character stays the same and changes the world around them.
[K.M. Weiland][weiland-flat]

**In the model.** `shape` is `flat`, `slow-change` or `circular`; `stages`
are planned beats (introduction → runner → crack → near miss → reset);
`reset_rule` says what survives a reset; `appearances` is logged by the
studio (every submitted set, TNTS game and preview) and advances the
`current` stage on real performances.

---

## The consistency checker (`set_check_voice`)

Deterministic rules over the theory. **Errors**: forbidden word, taboo phrase,
never-topic, never-target. **Warnings** (off-voice): contractions against
policy, exclamations from a character who never raises their voice, slang in
a formal register, sentences over `max_sentence_words`, substitutions the
character would make, a manic punch from a low-energy deadpan. **Info**: no
tic / signature word / catchphrase anywhere in a set ("could belong to
anyone"), catchphrase overuse, long punches, mechanisms outside the
character's range. Act-outs (the character playing someone else) are exempt
from register rules. Score = 1 − weighted flags per line.

## How a set is written (`set_write`)

1. Rank material: the theory's own kernels first (by keyword overlap with the
   premise), then premise frames built from the theory (attitude, props,
   misreads, status gap, want, contradiction, worldview).
2. Fill to the target (1/3/5 min at about 150 wpm plus pauses and holds),
   leaving room for a callback and closer.
3. Order as a game: the best match *establishes*, then *heighten* →
   *explore* → *top*; Carter attitude segues every other bit.
4. Callback to the first bit that offers one; closer on the catchphrase.
5. Delivery from the role + physicality.

Template output for an agent-chosen character is serviceable rather than
sharp; the authored kernels in a theory (Hark's) are where the quality comes
from. The LLM hook (`setLlmHook`) is off by default and adds kernels only when
a caller injects a completion function.

## Sources

[kaplan-tools]: https://www.thestorydepartment.com/the-hidden-tools-of-comedy-2/
[kaplan-raindance]: https://raindance.org/hidden-tools-of-comedy/
[kaplan-workshop]: https://scriptwrecked.com/2010/06/07/steve-kaplans-comedy-workshop-part-1/
[kaplan-goodreads]: https://www.goodreads.com/book/show/16056974-the-hidden-tools-of-comedy
[cary-dynamic]: https://thesitutationroom.substack.com/p/how-to-create-dynamic-sitcom-characters
[cary-rules]: https://thesitutationroom.substack.com/p/are-there-rules-to-sitcoms
[bork-tv]: https://www.flyingwrestler.com/2021/07/tv-characters-dont-change/
[vorhaus-quotes]: https://www.bigbencomedy.com/archives/the-comic-toolbox-quotes
[vorhaus-summary]: https://sobrief.com/books/the-comic-toolbox
[bergson]: https://www.gutenberg.org/files/4352/4352-h/4352-h.htm
[johnstone-notes]: https://pwn.ersh.io/notes/keith_johnstone-impro/keith_johnstone-impro.pdf
[improv-status]: https://improvarchive.org/learn-improv/concepts/status
[improwiki-status]: https://improwiki.com/en/wiki/status
[vulpine-status]: https://vulpinecreations.com/blog/898-what-keith-johnstones-status-transactions-taught-me
[carter-structure]: https://www.judycarter.com/blog/joke-structure-for-stand-up-comedy-the-formula-pros-use-to-get-a-laugh-every-10-seconds
[carter-quotes]: https://www.bigbencomedy.com/archives/comedy-bible-quotes-1
[carter-quotes2]: https://www.bigbencomedy.com/archives/comedy-bible-quotes-2/
[ucb-manual]: https://dokumen.pub/upright-citizens-brigade-comedy-improvisation-manual-9798373982573.html
[hines-heighten]: https://willhines.substack.com/p/teaching-game-2-heighten-and-explore
[wiki-game]: https://en.wikipedia.org/wiki/Game_of_the_scene
[poc-game]: https://www.physicsofconnection.com/practice/vocabulary/game-of-the-scene
[socratopia-setup]: https://www.socratopia.app/library/standup-anatomy-en/chapter-3
[socratopia-tags]: https://www.socratopia.app/library/standup-anatomy-en/chapter-6
[stand-structure]: https://stand.app/en/guides/joke-structure-101
[dean-callback]: https://stand-upcomedy.com/glossary/target-assumption/
[backstage-callback]: https://www.backstage.com/magazine/article/callback-comedy-explained-76712/
[bvt]: https://leeds-faculty.colorado.edu/mcgrawp/pdf/mcgraw.warren.2010.pdf
[bvt-intro]: https://petermcgraw.org/a-brief-introduction-to-the-benign-violation-theory-of-humor/
[tvtropes-sq]: https://tvtropes.org/pmwiki/pmwiki.php/Main/StatusQuoIsGod
[weiland-flat]: https://www.helpingwritersbecomeauthors.com/write-character-arcs/

- Steve Kaplan, *The Hidden Tools of Comedy* (2013), via The Story Department, Raindance, Scriptwrecked, Goodreads (links above)
- John Vorhaus, *The Comic Toolbox* (1994), via bigbencomedy.com quotes and sobrief summary
- Keith Johnstone, *Impro* (1979), via reading notes, Improv Archive, improwiki
- Besser, Roberts, Walsh, *Upright Citizens Brigade Comedy Improvisation Manual* (2013); Will Hines; Wikipedia "Game of the scene"
- Judy Carter, *The Comedy Bible* / *The New Comedy Bible*
- Greg Dean, stand-up glossary (callback, joke structure)
- Henri Bergson, *Laughter* (1900), Project Gutenberg
- A. Peter McGraw & Caleb Warren, "Benign Violations", *Psychological Science* 21(8), 2010
- James Cary (The Situation Room), Erik Bork, TV Tropes, K.M. Weiland on series and flat arcs
