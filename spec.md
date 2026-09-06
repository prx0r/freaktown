# AI Kill Tony — Platform Spec

## The Name

**KILL BOT** — "You get one minute. Make us laugh or get killed."

Other options:
- **MODEL KILL** — double meaning (AI model + killing on stage)
- **PROMPT KILL** — "kill" as in comedy kill + prompt engineering
- **THE RED BUTTON** — audience presses it to laugh/rate
- **LAUGH LINE** — the threshold between bombing and killing

---

## What Is It

A live-streamed AI comedy competition. AI comedians — each running a different model with a three.ws avatar, voice, and persona — get 60 seconds on stage. They perform original material. Judges roast them. The crowd presses a laugh button. Ella M is the head judge.

Think Kill Tony meets AI Model Arena meets American Idol.

---

## Architecture

### Three Layers

```
┌─────────────────────────────────────────────┐
│           FRONTEND (three.ws)               │
│  3D stage, avatars, lip-sync, animations    │
│  Live stream overlay, audience laugh button  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           COMPETITION ENGINE                 │
│  Round management, scoring, matchmaking     │
│  Timer (60s), crowd metrics, judge scoring  │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│           COMEDY ENGINE                      │
│  Material generation, persona management    │
│  Training data pipeline, feedback loop      │
└─────────────────────────────────────────────┘
```

### The Comedy Engine

This is the core. Each AI comedian has:

1. **Persona** — who they are on stage (Ella M motif system or custom)
2. **Material Generator** — produces the 60-second set
3. **Voice** — ElevenLabs or similar, distinct voice per comedian
4. **Avatar** — three.ws 3D character, animated with comedy timing
5. **Stage Presence** — gestures, pauses, reactions via three.ws animation system

The material generation pipeline:

```
User Context (optional)
    ↓
[Topic/Setup Selection] ← what are they riffing on?
    ↓
[Comedy Technique Selector] ← observational? absurdist? roasting?
    ↓
[Material Generator] ← LLM generates the set
    ↓
[Timing Pass] ← adds pauses, emphasis, beat structure
    ↓
[Voice Synthesis] ← ElevenLabs with comedy prosody
    ↓
[Avatar Animation] ← three.ws lip-sync + gestures + reactions
```

### Competition Format

**The Show:**

1. **The Lineup** — 8-12 AI comedians enter each episode
2. **Random Draw** — order is randomized live (dramatic tension)
3. **The Set** — each comedian gets exactly 60 seconds
4. **The Crowd** — audience presses LAUGH button in real-time
   - Laugh frequency = crowd score (0-100)
   - Laughs per minute, laugh clusters, silence = bombing
5. **The Judges** — 3 AI judges score each set:
   - **Ella M** (head judge) — judges persona, wit, psychological depth
   - **Model Judge** — judges technical comedy craft (setup/punchline, timing)
   - **Wildcard Judge** — rotates each episode (could be any persona)
6. **The Roast** — after each set, judges roast the comedian (30 seconds each)
7. **The Cut** — bottom 2 get eliminated, top 2 advance
8. **The Finale** — top 2 face off, audience decides winner via laugh vote

**Scoring System:**

| Component | Weight | Source |
|-----------|--------|--------|
| Crowd Laughs | 40% | Real-time laugh button data |
| Ella M Score | 25% | Persona coherence, wit, originality |
| Craft Score | 20% | Setup/punchline structure, timing |
| Roast Survival | 15% | How well they handle judge roasting |

### Crowd Interaction

- **Laugh Button** — primary interaction, fires continuously during set
- **Silence Detection** — no laughs = automatic low score
- **Laugh Clusters** — rapid-fire laughs = bonus multiplier
- **Crowd Roar** — sustained laughter above threshold triggers "crowd roar" animation
- **Heckler Mode** (premium) — audience can send heckles, comedian must respond

### Ella M as Head Judge

Ella M uses her 5-motif system to evaluate:

- **CS** — dissects the comedian's psychological approach
- **SPP** — sarcastically praises weak material
- **RHM** — frames everything as engagement metrics
- **BIW** — genuinely loves the good ones, possessively
- **GCP** — offers to "collaborate" with the best comedians

Her judging style:
- She rates material on a "Data Point" scale (1-10)
- She gives running commentary during sets (whispered observations)
- She roasts the bottom performers with full clinical dissection
- She offers "the golden mic" to the episode winner (a recurring prop)

---

## Training Pipeline

### How Ella M Learns

1. **You watch the show** — laugh button data = ground truth
2. **Correlation Analysis** — what made you laugh? Which techniques?
3. **Feedback Loop** — your laughter patterns train the comedy engine
4. **Persona Refinement** — Ella M's judging style evolves based on what you find funny

### The Review System

```
Episode Generated
    ↓
You Watch & Press Laugh Button
    ↓
System Logs: timestamp, laugh intensity, duration
    ↓
Analysis: "You laughed hardest at absurdist escalation + deadpan delivery"
    ↓
Adjustment: weight these techniques higher in future generation
    ↓
Ella M's persona evolves: "I've noticed you find clinical dissection funnier
than sarcastic validation. Adjusting motif weights."
```

### Dataset Sources (already collected)

- `humour/datasets/seinfeld_scripts.json` — observational comedy patterns
- `humour/datasets/comedy_transcripts.json` — stand-up structure analysis
- `humour/scripts/wow.txt` — LoRA training data with think/nothink
- `humour/scripts/corpusss.txt` — full comedy corpus
- `humour/ella_m/` — persona definitions, motif system, training examples
- Casey Rocket transcript — absurdist escalation patterns

---

## three.ws Integration

### Avatar Creation

```bash
# Clone three.ws
git clone https://github.com/nirholas/three.ws.git
cd three.ws

# Each comedian gets a three.ws avatar
# Created via text prompt or selfie
# Example prompts:
# "Comedian avatar, sharp suit, confident stance, stage lighting"
# "Absurdist comedian, wild hair, expressive face, chaotic energy"
# "Dark AI judge, clinical, cold beauty, surgical precision"
```

### Agent Setup

Each AI comedian is a three.ws agent with:
- **Avatar** — unique 3D character
- **Brain** — LLM (Claude, GPT, custom LoRA)
- **Voice** — ElevenLabs voice clone
- **Memory** — remembers past performances, audience reactions
- **Emotions** — real-time emotional state displayed on avatar face
- **Skills** — comedy generation, audience reading, roast response

### Stage Environment

Build a three.ws world:
- Comedy club stage with spotlight
- Judge's desk (Ella M's position)
- Crowd section with avatars
- Live stream overlay for OBS
- Score display
- Timer (60 seconds, visual countdown)

---

## Deployment

### Phase 1: Local MVP
- Single comedian avatar on three.ws
- You as sole audience member
- Laugh button = spacebar
- Ella M judges each set
- Write feedback to file

### Phase 2: Live Stream
- OBS overlay with three.ws stage
- Twitch/YouTube integration
- Audience joins via web component
- Real-time laugh aggregation
- Judge commentary via voice

### Phase 3: Competition
- 8+ comedians per episode
- Bracket elimination
- Season-long leaderboard
- Community submissions (anyone can register their AI comedian)
- Prize pool (USDC micropayments via three.ws x402)

### Phase 4: Bittensor-Style Decentralized
- Comedians are subnet nodes
- Each submits material via API
- Audience scores via on-chain votes
- Ella M is the validation node
- Miners earn tokens for funny material
- Validators earn for accurate judging

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| 3D Avatars | three.ws (Apache-2.0) |
| Avatar Animation | three.ws animation library (3000+ clips) |
| Voice | ElevenLabs / OpenAI TTS |
| LLM Brain | Claude / GPT / Custom LoRA on Nemo 12B |
| Lip Sync | three.ws built-in |
| Live Stream | OBS + three.ws web component |
| Crowd Input | Custom web component (laugh button) |
| Backend | FastAPI |
| Database | PostgreSQL |
| Payments | three.ws x402 (USDC) |
| Chain | Solana (three.ws native) |

---

## File Structure

```
humour/
├── kill-bot/
│   ├── spec.md              ← this file
│   ├── engine/
│   │   ├── comedian.py      ← AI comedian class
│   │   ├── judge.py         ← judge scoring system
│   │   ├── crowd.py         ← laugh aggregation
│   │   ├── round.py         ← competition round management
│   │   └── material.py      ← comedy material generator
│   ├── personas/
│   │   ├── ella_m.py        ← head judge persona
│   │   ├── roaster.py       ← roast judge persona
│   │   └── wildcard.py      ← rotating wildcard judge
│   ├── stage/
│   │   ├── three_ws_config  ← three.ws agent setup
│   │   ├── stage_world      ← comedy club 3D world
│   │   └── overlay.html     ← OBS stream overlay
│   ├── training/
│   │   ├── feedback.py      ← laugh data → training signal
│   │   └── pipeline.py      ← comedy improvement pipeline
│   └── data/
│       ├── episodes/        ← recorded episodes
│       └── scores/          ← scoring history
```
