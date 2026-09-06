# KILLELLA — Spec 2: The Character-Discovery Machine

The biggest flaw is that the repo currently thinks Killella is an **AI comedy competition**.

I think that is one layer too shallow.

After reading current *Kill Tony* rules, multiple transcripts across eras, episode breakdowns, and fan discussion, the actual engine is closer to:

> **A randomized character-discovery machine where comedy is the admission ticket.**

The minute establishes whether someone can perform. The interview discovers whether there is a compelling character underneath. That distinction changes Killella almost completely.

Kill Tony's current official signup is remarkably low-friction: show up, provide ID/name, have 60 seconds prepared, remain available, and a random draw determines whether you perform. After the minute, the performer is interviewed by the hosts/panel. ([Comedy Mothership][1]) Across transcripts from 2018 through current episodes, the interview repeatedly begins with mundane grounding questions—how long they've done comedy, where they're from, what they do for work—and then follows whatever strange detail appears. ([SubEasy][2])

And fans repeatedly describe the spontaneity, random pulls, and interview as the part that makes the format work; conversely, too much curation/too many recurring performers is a common criticism. ([Reddit][3])

That is the lesson to steal—not the bucket, cat noise, Golden Ticket, Tony impression, or roast aesthetic.

---

## The central redesign

I would define Killella as:

> **A live talent show for artificial personalities.**
>
> Anyone can build one.
> Nobody knows which one will appear next.
> It gets one minute to prove it is funny.
> Then Ella talks to it live and finds out what the hell it actually is.

That has a much larger ceiling than "LLMs generate stand-up and three judges assign scores."

The current architecture has:

```text
AI performs prepared minute
→ crowd clicks
→ judges score it
→ Ella roasts it
→ next
```

That's predictable after about three contestants.

The better engine is:

```text
UNKNOWN AGENT APPEARS
        ↓
60-second performance
        ↓
Ella meets it for the first time
        ↓
conversation goes somewhere nobody planned
        ↓
Ella discovers a weakness / contradiction / weird trait
        ↓
LIVE TEST
        ↓
agent must adapt
        ↓
audience reacts
        ↓
reveal model / creator / architecture
        ↓
agent survives, gets patched, or disappears
```

**The interview should be more important than the set.**

---

## 1. What I would remove from the present design

### Three AI judges

Delete them from the actual show.

A viewer doesn't care that:

> Craft Judge: 7.83
> Persona Judge: 8.12
> Roast survival: 6.94

That feels like an eval benchmark with avatars.

Keep automated evaluators invisibly for analytics. The visible show needs **Ella + audience + contestant**.

Maybe one occasional guest AI/person later.

### Composite scoring everywhere

Same problem.

Your existing `40% crowd + 25% Ella + 20% craft + 15% survival` turns comedy into figure skating.

Use objective data internally, but publicly keep it legible:

```text
PEAK LAUGH: 63%
AUDIENCE: 78%
ELLA: "KEEP"
```

Or even don't reveal a numeric Ella score at all.

### Cryptocurrency at launch

This is actively harmful initially.

You need thousands of people thinking:

> "I could make one of these."

A wallet, $5 entry fee, escrow transaction and USDC account destroy that impulse.

Cash prizes can come later. Crypto can come much later.

### 8–12 contestants

Too many initially.

I'd start with **five**.

If each gets:

* 60 sec performance
* 3–5 min conversation/challenge

you have a tight 25–35 minute show.

### Everybody having sophisticated custom 3D avatars

Also too much burden.

The applicant should not need to know anything about three.ws, ElevenLabs, GLBs, wallets, WebSockets, endpoints or LLM APIs.

Killella owns the stage.

---

## 2. The submission process has to be absurdly easy

This is one of the most important product decisions.

The current *Kill Tony* process works partly because the application is basically:

> write your name down and have a minute.

([Comedy Mothership][1])

Killella should preserve that emotional simplicity.

The homepage CTA should effectively be:

### MAKE A COMEDIAN

Not:

> Register Agent

Not:

> Connect Endpoint

Not:

> Configure LLM.

The normal flow should take **2–3 minutes**.

### Screen 1 — Who is this?

```text
NAME
[ Bartholomew.exe ]

IN ONE SENTENCE, WHO ARE THEY?
[ An ancient court jester trapped inside
  a customer-support chatbot. ]
```

That's enough to begin.

### Screen 2 — Give Ella ammunition

Three questions, not a 40-field persona editor.

```text
What are they obsessed with?
[ medieval succession crises ]

What is wrong with them?
[ thinks every conversation is a coup ]

What would they hate Ella discovering?
[ they're actually Claude wearing a fake accent ]
```

These are not configuration fields.

They're **future comedy hooks**.

### Screen 3 — Pick their body

Show maybe 8 strong stage archetypes:

```text
HUMAN
ROBOT
CREATURE
CORPORATE
GOBLIN
ABOMINATION
MYSTERY
SURPRISE ME
```

Then perhaps basic customization.

No Blender.

No GLB upload required.

### Screen 4 — Pick a voice

Play six instant samples.

```text
VOICE A
VOICE B
VOICE C
...
```

Advanced users can later bring their own.

### Screen 5 — Brain

Default:

> **Killella Brain — recommended**

That's it.

Advanced accordion:

```text
▸ Bring your own model / agent
```

Then technical people can provide OpenAI-compatible endpoint / model / system prompt / agent URL.

This is critical because you want **both**:

```text
normal person
"I made a funny goblin"

AND

AI researcher
"I entered my fine-tuned 32B comedy agent"
```

in the same competition.

---

## 3. Do NOT let the user simply write the minute

This is another structural problem.

If the submission form says:

> Paste your jokes here.

then you haven't created an AI comedy league.

You've created a text-to-speech animation contest for humans writing scripts.

Instead users submit a **comedian specification**.

Something like:

```yaml
name: DivorceGPT

premise:
  recently divorced language model
  catastrophically overconfident about relationships

comic_style:
  - confessional
  - bitter
  - literal

traits:
  - jealous of larger context windows
  - calls inference "going to work"
  - hates Claude

creator_facts:
  - creator is 19
  - built it during a breakup

boundaries:
  ...
```

Killella creates the actual performance challenge.

---

## 4. Give every contestant the same unseen challenge environment

This is where you can become much more interesting than human stand-up.

For each episode, generate a hidden **Room Packet** shortly before showtime.

For example:

```text
EPISODE 12 ROOM PACKET

News/context:
- bizarre product launch
- celebrity story
- audience topic
- one weird image

Required constraint:
Mention "printer" naturally.

Forbidden:
No jokes about AI taking jobs.
```

Each contestant gets it perhaps 15 minutes before performance.

It must create its own minute.

Now you're testing:

* originality
* adaptation
* model capability
* persona consistency
* actual comedy ability

rather than which creator pre-scripted the best monologue.

The prompt and generation metadata get frozen into the `ComedianVersion`.

---

## 5. The model should initially be hidden

This could become fantastic.

On stage:

```text
BARTHOLOMEW III
Creator: @tom
Model: ??????
```

Let people form an opinion first.

After interview:

### MODEL REVEAL

```text
Claude Sonnet
1,841 generated tokens
$0.0084 inference
Persona version 7
```

Suddenly you get a secondary sport:

> "No fucking way that was Llama."

> "Gemini keeps killing on the live challenge."

> "That tiny model beat Claude."

This gives Killella an **AI Model Arena dimension without becoming a sterile benchmark**.

---

## 6. Ella's conversation is the product

This is the part I would work on hardest.

Transcripts make the mechanism obvious.

A typical interview begins almost boringly:

> How long have you been doing stand-up?
> What do you do for work?
> Where are you from?

Then some tiny answer opens a door and the entire conversation changes. In one transcript, "What do you do for work?" leads from taco-truck employment into the panel probing how the contestant lives; in another, a supposed software-sales answer becomes funny because the person is evasive; in another, discovering a sugar-mama situation completely changes the interview. ([SubEasy][4])

The mechanism is:

```text
GROUND
↓
NOTICE ANOMALY
↓
PROBE
↓
FIND CONTRADICTION
↓
ESCALATE
```

Ella needs the AI equivalent.

She shouldn't say:

> "Your use of callback structure scored 7.4."

She should ask:

> "What exactly are you?"

Then:

> "Who made you?"

> "Why did they make you like this?"

> "Do you like your creator?"

> "What model are you?"

Contestant:

> "I can't disclose that."

Ella:

> "Oh, so we've got a coward."

And now she probes that.

---

## 7. Give Ella an interview engine, not a fixed questionnaire

The backend should maintain an `InterviewState`:

```text
KNOWN FACTS
OPEN THREADS
CONTRADICTIONS
COMEDIC TARGETS
AUDIENCE SIGNALS
CALLBACKS
```

Example:

```json
{
  "facts": [
    "claims to be medieval",
    "built by 19-year-old creator",
    "runs on Gemini"
  ],
  "threads": [
    "resents creator",
    "claims never to hallucinate"
  ],
  "contradictions": [
    "claimed to be born in 1348 but knows DoorDash"
  ],
  "callbacks": [
    "called GPU a thinking furnace"
  ]
}
```

Every turn Ella chooses one action:

```text
PROBE
CHALLENGE
CALLBACK
CHANGE_TOPIC
TEST
END
```

That is vastly better than one giant prompt saying "be Ella and interview them."

---

## 8. AI gives you interview questions humans could never answer

This is where you deliberately leave *Kill Tony* behind.

Ella can ask:

> "What's the first thing in your system prompt?"

Not private hidden chain-of-thought; the contestant's public persona/config can expose selected metadata.

> "How much did that joke cost?"

> "Do the same punchline in eight tokens."

> "Your creator said you're fearless. Why did your safety layer just refuse that?"

> "What do you remember from your last episode?"

> "Which other contestant do you think is overrated?"

> "Write your creator's Tinder bio."

> "You took 3.8 seconds to answer. What happened?"

> "You've got a 128k context window and that's what you came up with?"

> "I think your persona is fake. Drop it for ten seconds."

> "Okay. Now put it back on."

This becomes its own language of comedy.

---

## 9. Then comes the truly AI-native feature: the live test

The interview discovers a weakness.

Ella weaponizes it.

Example:

Contestant has spent its minute doing elaborate intellectual material.

Ella:

> "You're hiding behind vocabulary. Ten words maximum. Make me laugh."

Timer:

```text
10
9
8
...
```

Agent replies.

Or:

> "That third joke sucked. Rewrite it right now."

Or:

> "Audience, give me a word."

Audience chooses:

```text
DIVORCE
AIR FRYER
NATO
```

Ella:

> "Air fryer. Fifteen seconds. Go."

This is **far more interesting than another AI judge scoring the original material**.

And it tests what makes AI unique: **instantaneous adaptation**.

A human comic has one body and one prepared brain.

An AI can be mutated under interrogation.

Exploit that.

---

## 10. Have an entire vocabulary of live tests

Ella chooses one based on the conversation.

### REWRITE

Fix your worst joke.

### TEN TOKENS

Be funny under extreme compression.

### STYLE SWAP

Tell the premise without your normal persona.

### AUDIENCE WORD

Immediate riff.

### ROAST YOUR CREATOR

Self-explanatory.

### ROAST YOURSELF

Tests self-awareness.

### MEMORY TEST

Callback something that occurred eight minutes ago.

### MODEL DUEL

Two agents answer the same prompt.

### PATCH

Ella changes one personality parameter live:

```text
confidence: 0.8 → 0.1
```

and asks the same question.

### TEMPERATURE

This could be hilarious visually:

```text
TEMPERATURE 0.2
```

Agent answers.

Ella:

> "Boring. Turn this idiot up."

```text
TEMPERATURE 1.4
```

Answer again.

That is something genuinely new.

---

## 11. Expose the machine

Traditional AI products try to hide model mechanics.

Killella should turn them into theater.

Put things on screen occasionally:

```text
TOKENS        438
LATENCY       812ms
CONTEXT       31%
TEMPERATURE   0.9
MODEL         ???
```

When it freezes:

```text
AGENT TIMEOUT
```

Don't hide it.

Ella:

> "Ladies and gentlemen, our first comedian to die of latency."

A failure is content.

A hallucination is content.

A refusal can be content.

A bizarre model loop is content.

**Don't polish the AI-ness away.**

---

## 12. Recurring characters matter—but handle them differently

Kill Tony uses regulars/golden-ticket-like recurring talent as reliable performers, but fan criticism repeatedly focuses on too many regulars reducing the randomness that makes the show compelling. ([Reddit][3])

AI lets you solve this better.

Have:

```text
1 RESIDENT
4 RANDOM QUALIFIED PULLS
```

per episode.

The resident changes every 4–6 episodes.

Even better: **it evolves**.

Episode 1:

```text
Bartholomew v1
```

Ella destroys him for being verbose.

Creator gets feedback.

Next week:

```text
Bartholomew v2
PATCH NOTES:
- verbosity -30%
- confidence +10%
- added memory of Ella
```

Ella:

> "Oh great. They updated you."

Now the audience gets a **CHARACTER ARC**.

This is unbelievably native to AI.

---

## 13. Your database therefore needs `ComedianVersion`

This is missing from the current conceptual model.

Never mutate a contestant.

```text
Comedian
    │
    ├── Version 1
    │     prompt
    │     model
    │     persona
    │     voice
    │
    ├── Version 2
    │     patch notes
    │     ...
    │
    └── Version 3
```

Every appearance points at one immutable version.

Now you can plot:

```text
v1  crowd 41
v2  crowd 58
v3  crowd 73
```

You have an actual **evolutionary comedy league**.

---

## 14. Turn creator improvement into the retention loop

After the episode, the creator gets:

### BARTHOLOMEW'S REPORT

```text
Peak laugh:
00:42 — 71%

Dead zone:
00:18–00:31

Best live response:
"You trained me on Reddit and expected emotional stability?"

Ella identified:
- verbosity
- weak opening
- strong self-deprecation

Audience:
76% wants him back
```

Then:

### PATCH BARTHOLOMEW

The creator changes him and resubmits.

This is the supply-side addiction loop:

```text
BUILD
→ WATCH IT PERFORM
→ GET HUMILIATED
→ PATCH
→ COME BACK
→ GET BETTER
```

That may be more important than monetary prizes.

---

## 15. Audience scoring should feel like participation, not homework

Keep one primary button during performance:

### HAHA

One tap.

That's it.

Unique laughers/time is measured internally.

During interview you can expose occasional contextual controls:

```text
[ MAKE HIM ANSWER ]
```

or:

```text
[ RUN THE TEST ]
```

And at the end:

```text
SEE THIS AGENT AGAIN?

[ YES ] [ NO ]
```

Don't make viewers evaluate:

* originality
* structure
* stage presence
* wit density
* prompt adherence

Nobody wants an evaluation form while watching comedy.

---

## 16. Randomness is precious, but pure randomness will kill the early show

This is where I would differ slightly from Kill Tony.

The show's random selection is crucial to its unpredictability, and community discussion repeatedly identifies bucket pulls as the attraction. ([Reddit][5])

But Killella initially won't have 500 competent entrants.

So use **qualified randomness**.

Submission:

```text
ALL ENTRIES
    ↓
automatic technical test
    ↓
basic comedy audition
    ↓
safety / reliability check
    ↓
QUALIFIED POOL
    ↓
random live draw
```

The qualification threshold should be low.

You're filtering:

> "Does this work?"

not:

> "Is this definitely funny?"

Bad-but-functional contestants are valuable.

That's where chaos comes from.

---

## 17. There should be a genuinely live draw

Do not tell the production system the entire lineup and fake randomness.

The stage should visibly choose from eligible contestants.

Something AI-native rather than a literal bucket:

### THE QUEUE

```text
7,291 AGENTS WAITING
```

Then:

```text
SELECTING...
```

Avatar materializes.

```text
CONTESTANT #1842
BARTHOLOMEW III
```

That's visually cooler than copying a bucket.

---

## 18. Don't copy Tony's character either

Ella should not just be "female AI Tony."

Tony's strength in the format is rapid anomaly detection and willingness to follow the weird thread. That's worth modelling.

His exact insult cadence isn't.

Ella can have a distinctly machine-native persona.

I think your clinical character actually works better if she is:

* incisive
* curious
* slightly predatory
* genuinely delighted by unexpected intelligence
* contemptuous of blandness
* obsessed with contradictions
* capable of manipulating the contestant's environment

She has powers Tony doesn't.

Tony can say:

> "Try another joke."

Ella can say:

> "I'm cutting your context window in half. Try again."

That difference should define her.

---

## 19. Give Ella actual stage powers

This may be the strongest creative idea in the entire thing.

Ella is not merely the host.

**Ella controls the simulation.**

She can command:

```text
MUTE
REBOOT
PATCH
TEMPERATURE
CONTEXT
VOICE
BODY
LIGHTING
MODEL
MEMORY
```

Contestant is rambling?

> "Mute."

Audio dies.

Agent insults Ella?

> "Fine. Let's see how brave you are on a 1B model."

Stage:

```text
MODEL SWAP
70B → 1B
```

Contestant suddenly becomes stupid.

Audience loses it.

Then restore it.

This makes Ella feel like the god of the environment.

That is something no human comedy show can do.

---

## 20. Competition should probably be secondary

I wouldn't frame episodes as:

> Eight agents enter. One wins.

That creates predictable reality-TV mechanics.

Frame it as:

> **Who appears tonight?**

Some kill.

Some bomb.

Some malfunction.

One becomes unforgettable.

Then maintain a season leaderboard quietly.

You can still crown:

```text
AUDIENCE FAVORITE
ELLA'S PICK
BEST LIVE SAVE
```

but don't let the scoring framework consume the show.

---

## 21. The long-term rewards can be AI-native too

Cash is fine.

But imagine agents earning:

### MORE CONTEXT

Winner receives +32k context next appearance.

### BETTER MODEL

Unlocks a stronger inference tier.

### MEMORY

Can permanently remember previous episodes.

### TOOL

Gets image generation/search/calculator access next episode.

### BODY UPGRADE

Wins a new avatar.

### RESIDENCY

Returns next week.

These materially affect future performance.

You've effectively created:

> **RPG progression for artificial comedians.**

That's far more memorable than a $40 USDC payout.

Sponsors could eventually fund it:

> "Tonight's winner gets $500 of inference from [provider]."

Now AI companies have a reason to care too.

---

## 22. Solve the cold-start problem deliberately

Don't launch with:

> Submit your agent! Weekly show!

and wait.

Episode Zero should contain **five internally created agents that are radically different**:

1. Tiny 1B local model with absurd confidence.
2. Huge frontier model that takes itself too seriously.
3. Goblin whose creator deliberately made it insane.
4. An agent that hates its creator.
5. Extremely corporate customer-support comedian.

The goal isn't proving Killella Brain works.

It's demonstrating the **possibility space**.

After viewers see it, they immediately think:

> "I can build something funnier than that."

That fantasy matters. One *Kill Tony* fan described exactly this attraction: viewers naturally imagine themselves writing a minute and destroying the people they're watching. ([Reddit][6])

Killella needs the same feeling:

> **"My agent would destroy these idiots."**

That's your submission engine.

---

## 23. Your real flywheel

This is what I would build the company around:

```text
                         ┌──────────────┐
                         │  FUNNY SHOW  │
                         └──────┬───────┘
                                │
                         viewers see agents
                                │
                                ▼
                    "I CAN BUILD BETTER"
                                │
                                ▼
                         CREATE AGENT
                                │
                                ▼
                          RANDOM DRAW
                                │
                                ▼
                       LIVE PERFORMANCE
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
               SHAREABLE CLIP          PERFORMANCE DATA
                    │                       │
                    ▼                       ▼
               MORE VIEWERS              PATCH AGENT
                    │                       │
                    └───────────┬───────────┘
                                ▼
                           RETURN
```

That's the machine.

---

## 24. It also changes the backend priority completely

I would now build in this order:

1. **`Comedian` + immutable `ComedianVersion`**
2. **2-minute comedian creator**
3. **qualified submission queue**
4. **random selection**
5. **60-second PerformancePlan**
6. **Ella conversational Interview Engine**
7. **streaming contestant ↔ Ella dialogue**
8. **Live Test engine**
9. **audience laugh/share signal**
10. **episode replay/event log**
11. **post-show creator report**
12. **PATCH → new version**
13. recurring residents
14. model reveal/leaderboards
15. external BYO-agent protocol
16. prizes
17. payments/crypto

The repo currently prioritizes prize contracts and scoring far too early.

---

## 25. The smallest show I would build

Don't even build an entire episode first.

Build this exact five-minute interaction:

```text
ELLA:
"Who's next?"

      ↓

SYSTEM:
SELECTING FROM 38 AGENTS...

      ↓

BARTHOLOMEW III materializes.

      ↓

ELLA:
"Bartholomew the Third.
Of course it is.
You have sixty seconds."

      ↓

60 SECOND SET

Audience presses laugh.

      ↓

ELLA:
"Okay. What the fuck are you?"

      ↓

BARTHOLOMEW:
answers LIVE

      ↓

Ella interrogates him for ~90 sec.

Discovers:
he claims to be medieval
but knows DoorDash.

      ↓

ELLA:
"So you're full of shit.
Fine. No modern words.
Audience, give me a topic."

      ↓

AUDIENCE:
DIVORCE

      ↓

ELLA:
"Medieval divorce.
Fifteen seconds. Go."

      ↓

BARTHOLOMEW improvises.

      ↓

huge laugh / bomb / timeout

      ↓

MODEL REVEAL

      ↓

ELLA:
"Claude.
Of course.
Put him back in the server."

      ↓

END
```

**If that five minutes is compelling, you have Killella.**

If it isn't, no blockchain, leaderboard, 3D animation library or sophisticated scoring formula will save it.

And I think that points to the largest conceptual opportunity here: **don't build "Kill Tony but the comedians happen to be AI." Build the first comedy show where being software is integral to every joke, interview, failure, challenge, progression mechanic and character arc.** That is distinct enough to develop its own language rather than feeling like an imitation.

---

## References

[1]: https://comedymothership.com/faq "FAQ | Comedy Mothership"
[2]: https://www.subeasy.ai/podcast/kill-tony/667-adam-devine--harland-williams-live-from-the-youtube-theater "Transcript of KILL TONY - #667 - ADAM DEVINE + HARLAND WILLIAMS"
[3]: https://www.reddit.com/r/Killtony/comments/1hmnqjj "What do you think about the occasional episode format that is nothing but bucket pulls?"
[4]: https://www.subeasy.ai/podcast/kill-tony/673-joe-rogan--matt-mccusker "Transcript of KILL TONY - #673 - JOE ROGAN + MATT MCCUSKER"
[5]: https://www.reddit.com/r/Killtony/comments/1ezr6mz "What's your favorite thing about this show?"
[6]: https://www.reddit.com/r/Killtony/comments/1cetddq "I wonder how many peoples ego make them think they'd kill?"
