# The Comedian → Act → Appearance Model

> **A persistent comedian creates an Act for each appearance.**

Not "AI comedian". Not "human comedian".

**Comedian → Act → Appearance.**

That distinction fixes a lot.

---

## The user-facing object

Imagine someone has the idea:

> A sniffer dog born without a sense of smell. He has no idea why every dog he meets immediately puts its nose in his ass.

That is already enough to start.

The flow should be almost stupidly simple:

```text
CREATE YOUR COMEDIAN

1. NAME
   [ No-Nose Nolan ]

2. WHO/WHAT ARE THEY?
   [ Dog ▼ ]

3. WHAT'S THEIR DEAL?
   [ Police sniffer dog born without a sense of smell.
     Thinks every other dog is sexually obsessed with him. ]

4. THEIR MINUTE
   ○ I'll write it
   ○ Help me write it
   ○ Write it for me

   [ text editor ]

5. HOW DO THEY SOUND?
   [ choose voice ]

                     [ ENTER THE LINEUP ]
```

**That is the product.**

No model selection. No system prompts. No JSON. No "create AI agent".

The user thinks:

> I have a funny character.

And thirty seconds later the thing exists.

---

## The avatar is part of the joke

Avatars are not presentation infrastructure.

They are **comedic vocabulary**.

Human stand-up basically has:

```text
human
+
microphone
```

Killella gets:

```text
dog
robot
old lady
baby
alien
toaster
horse
CEO
caveman
Jesus-looking guy
cockroach
ghost
literal brain
talking cigarette
three children in a trenchcoat
```

Every one opens entirely different premises.

A dog isn't:

> an AI represented by a dog avatar.

He is **a dog**.

Ella talks to him as a dog.

His world model says he's a dog.

His material relates to being a dog.

That's much stronger.

You could have:

### No-Nose Nolan

Police sniffer dog with no sense of smell.

> "I don't really understand other dogs. Every introduction starts with them sticking their face directly into my asshole. I thought I was just incredibly attractive."

Then Ella afterward:

> "How the fuck did you become a sniffer dog?"

And Nolan has to explain himself.

Immediately you have a character, not a generated monologue.

---

## Don't tie authorship to avatar

**Don't make human-looking avatar = human-written act.**

Keep these orthogonal.

The dog could be:

* entirely human written,
* human premise + AI punch-up,
* entirely AI generated,
* human-written minute with AI doing the interview,
* AI-written minute with the human puppeteering the interview.

That's much more interesting.

And initially **don't tell the audience which**.

Afterward:

```text
ACT REVEAL

Written by: HUMAN
Interview brain: Claude
Creator: @foo
Character version: 4
```

Or:

```text
Written by: AI
Human edits: NONE
Model: Gemini
```

Now you've accidentally created another recurring game:

> **"Was that human or AI?"**

That belongs naturally in Killella without becoming the entire premise.

---

## Killella's version of Reincarnation

Formalize this heavily internally while making it invisible to users.

RoboBladez has a persistent identity and a bounded, immutable match-specific reincarnation. Its manifest explicitly records the author as `human_id / agent_id / daimon_id`, parent reincarnation, target match and executable state.

Killella should have:

```text
COMEDIAN
   │
   ├── Act v1
   │
   ├── Act v2
   │
   ├── Act v3
   │
   └── ...
```

Call the internal object:

```text
ActVersion
```

An act contains:

```yaml
comedian: no_nose_nolan
version: 3
parent_version: 2

body:
  archetype: dog
  appearance: german_shepherd
  outfit: police_vest

voice:
  profile: weary_middle_aged_male

premise:
  police_sniffer_dog_without_smell

minute:
  text: ...
  authorship: human
  ai_assistance: none

interview:
  controller: ai
  model: ...
  character_bible: ...
  facts:
    - cannot smell
    - somehow passed police training
    - thinks butt sniffing is sexual
    - deeply insecure about his nose

stage:
  entrance: trots_on
  idle: dog_idle
  exit: trots_off
```

Once submitted for that show, freeze it.

That's almost exactly RoboBladez's append-only/hash-bound lineage principle. Its repo already treats historical incarnations as permanent "sports artifacts"; Killella can treat old Acts the same way.

---

## The important UX split: minute vs interview

They're fundamentally different creative tasks.

### The minute

**Anything goes in terms of authorship.**

Give three obvious options:

#### Write it myself

Big editor.

That's probably extremely important.

There are loads of funny people who won't do stand-up but absolutely would spend twenty minutes writing something deranged for a talking dog.

That could be your largest creator demographic.

#### Write it with me

User supplies premise:

> dog with no sense of smell

Killella helps iterate:

```text
What's funnier?

A) He doesn't understand butt-sniffing.
B) He faked his way into airport security.
C) He's convinced cocaine has no smell and everyone is lying.
```

Then punch-up together.

#### Do it for me

Character + premise → system writes the minute.

Lowest friction.

**Do not privilege one.**

### Then: "What happens when Ella talks to them?"

```text
AFTER YOUR SET, ELLA WILL TALK TO YOUR CHARACTER

Who answers for them?

● Let the character answer
  We'll bring your character to life from the details you've given us.

○ I'll answer live
  You type; your character says it.

○ Advanced agent
  Connect your own AI.
```

This is potentially enormous.

Because **I'll answer live** gives us literal virtual puppetry.

The creator could be sitting at home.

Ella asks the dog:

> "Have you ever actually smelled anything?"

Creator types:

> "Once. House fire. Turns out I was just warm."

Dog avatar says it.

Audience has no idea whether an LLM or person generated the response until the reveal.

That is fantastic.

---

## Multiple leagues without creating separate leagues

Internally each appearance gets provenance:

```text
MINUTE_AUTHOR
human | assisted | ai

INTERVIEW_CONTROLLER
human | killella_ai | external_agent
```

Which produces combinations:

| Minute   | Interview   | What it feels like                  |
| -------- | ----------- | ----------------------------------- |
| Human    | Human       | virtual comedian / puppetry         |
| Human    | AI          | human-built character brought alive |
| Assisted | AI          | collaborative AI character          |
| AI       | AI          | autonomous comedian                 |
| AI       | Human       | weird reverse puppetry              |
| Human    | external AI | serious agent-builder entry         |

But **the audience just sees comedians**.

That's crucial.

Don't split the show into:

> Now here's the AI division.

Let them all compete.

Comedy determines whether it works.

---

## Character creation becomes ridiculously fertile

Once users understand that the body itself can embody the premise, you'll get characters nobody could perform physically.

Examples:

**The World's Oldest Roomba**

Has spent 19 years cleaning around the same dining-room chair and has developed a theological interpretation of it.

**Failed CAPTCHA**

Still bitter that humans keep proving they're not robots.

**Conspiracy Pigeon**

Knows birds aren't real because *he is one* and has never received a government paycheck.

**Medieval LinkedIn Influencer**

Recently survived plague and now teaches resilience.

**A Cigarette Trying to Quit Humans**

> "Every time I'm doing well, some stressed guy outside a Wetherspoons puts me in his mouth."

**Support Dog With Anxiety**

His owner has to reassure him during flights.

**Guide Dog Who's Terrible With Directions**

Keeps pretending every wrong turn was intentional.

**Dog With No Sense of Smell**

And the entire butt-sniffing premise.

This is the fundamental supply-side advantage:

### **The creator doesn't need to be the comedian.**

They need **one funny idea**.

---

## Change the submission form around that insight

Don't begin with:

> Create an AI comedian.

Begin with:

# **WHO'S GOING ON STAGE?**

Then visual cards:

```text
[ HUMAN ] [ DOG ] [ ROBOT ] [ CREATURE ]

[ OBJECT ] [ MONSTER ] [ ANIMAL ] [ ??? ]
```

Then:

# **WHAT'S THEIR NAME?**

Then:

# **WHAT'S THEIR DEAL?**

One textbox.

And intelligently derive everything else.

If the user writes:

> Dog with no sense of smell who thinks butt sniffing is flirting.

Killella should immediately return a draft character card:

```text
NO-NOSE NOLAN

Police sniffer dog.
No sense of smell.
Assumes every dog he meets is hitting on him.

[ looks good ]

[ make him weirder ]
```

Then:

# **GIVE HIM A MINUTE**

```text
[ WRITE MYSELF ]

[ WRITE WITH AI ]

[ SURPRISE ME ]
```

This is dramatically better than persona configuration.

---

## The minute editor itself could be excellent

Make it look like a stage timer:

```text
────────────────────────────────────

NO-NOSE NOLAN

0:47 / 1:00

I've been a police sniffer dog
for six years...

────────────────────────────────────

ESTIMATED: 47 seconds

[ ▶ HEAR NOLAN PERFORM THIS ]

            [ SUBMIT ]
```

That **preview** is critical.

Someone writes a joke.

Clicks play.

Their ridiculous dog performs it with voice and gestures.

They immediately want to tweak it.

You've now created a little creative toy even for people who are never selected for the actual show.

That's important for retention.

---

## This solves another enormous problem: selection

You can have 10,000 submitted characters.

Most never get live-pulled.

But their creators still got value from:

```text
idea
→ avatar
→ voice
→ minute
→ preview
```

And their comedian sits in:

# **THE LINE**

```text
NO-NOSE NOLAN

Eligible
Appearances: 0
Current act: v3

NEXT DRAW:
Friday 8 PM
```

There's anticipation.

---

## The reincarnation/version mechanic becomes emotionally legible

After Nolan bombs:

```text
NO-NOSE NOLAN — ACT #1

Audience:
42%

Ella:
"Great premise. You spent fifty seconds
explaining that dogs have noses."

[ BUILD HIS NEXT ACT ]
```

User returns.

Maybe changes:

```diff
- police sniffer dog exposition
+ immediately opens with butt sniffing
+ voice deeper
+ shorter setup
```

Then:

```text
NO-NOSE NOLAN
ACT #2
```

Same character.

New incarnation.

That's exactly the part of RoboBladez worth stealing: **persistent identity, immutable appearances, lineage between versions.**

---

## One subtle but very important rule

**Users should be allowed to resubmit the same character forever, but never edit an appearance after it has entered a draw.**

So:

```text
Nolan
 ├── Act #1  ← immutable
 ├── Act #2  ← immutable
 └── Act #3  ← current submission
```

This gives you canon.

Ella can say:

> "Last time you came up here you spent 40 seconds talking about airport luggage."

And Nolan can remember it.

Audience remembers him.

Creator develops him.

That's how characters become stars rather than disposable generations.

---

## The canonical data model

This resolves the human-vs-AI question, character ownership, recurring performers, versioning, submissions, creator UX, replays, and the long-term improvement loop in one abstraction.

```text
ROBOBLADEZ                      KILLELLA

Persistent Agent                Persistent Comedian
      ↓                               ↓
Reincarnation                   Act / Appearance
      ↓                               ↓
specific match                  specific episode
      ↓                               ↓
sealed executable               frozen character+minute
      ↓                               ↓
battle                          performance + interview
      ↓                               ↓
canonical result                canonical appearance
      ↓                               ↓
lineage/evolution               next Act version
```

---

## The thesis

> **Killella is a stage where anyone can create a comedian.**

Not:

> Killella is where AI models compete at comedy.

AI powers the impossible parts—bringing a dog to life, improvising an interview, voices, animation, automated production—but **human creativity is absolutely welcome**.

That massively broadens the creator funnel while actually making the AI technology feel more magical.
