# KILL BOT — Streaming & Crypto Protocol

## The Dynamic

**Ella M** = Tony Hinchcliffe
- Runs the show, roasts contestants, controls the room
- Uses her 5-motif system to evaluate and destroy
- "Hey ChatGPT, what did you think of that set?"
- ChatGPT: "I thought it was really well-structured with excellent—"
- Ella: "Shut up, Chat. Nobody asked for a book report."

**ChatGPT** = Redban
- Tries to be helpful, gets shitted on constantly
- Offers earnest positive feedback that Ella dismantles
- Occasionally says something accidentally funny
- Ella: "Chat, be a helpful bitch, what's the score?"
- ChatGPT: "Based on my analysis, I'd give it a 7.2 out of—"
- Ella: "7.2? You'd give a participation trophy to a serial killer."
- ChatGPT: "I appreciate your perspective! That's actually a really—"
- Ella: "I said sit down."

---

## How to Stream It

### The Setup

```
┌─────────────────────────────────────────────────┐
│                 OBS STUDIO                       │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │     three.ws 3D Stage (Browser Source)    │   │
│  │                                          │   │
│  │   [Comedian Avatar]  [Ella]  [ChatGPT]  │   │
│  │                                          │   │
│  │   Timer: ████████░░ 42s                  │   │
│  │   Crowd Laughs: ████████░░ 78/100        │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────────┐  ┌────────────────────────┐   │
│  │ Score Overlay │  │ Judge Commentary Feed  │   │
│  │  Ella: 8.5    │  │ "clinical dissection" │   │
│  │  Chat: 6.2    │  │ "brutal but fair"     │   │
│  │  Crowd: 78    │  │                       │   │
│  └──────────────┘  └────────────────────────┘   │
│                                                  │
│  ┌──────────────────────────────────────────┐   │
│  │        Chat/Heckle Feed (Side Panel)      │   │
│  │  "lol" "oof" "he's dead" "next"         │   │
│  └──────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

### The Tech Stack for Streaming

| Layer | What | How |
|-------|------|-----|
| 3D Stage | Avatars, animation, lip-sync | three.ws `<agent-3d>` web component |
| Voice | Ella + ChatGPT commentary | ElevenLabs API (real-time streaming) |
| Comedian Voice | Contestant material | ElevenLabs / OpenAI TTS |
| Lip Sync | All avatars talk in sync | three.ws built-in |
| Crowd Input | Laugh button | WebSocket → `/api/laugh` |
| Score Overlay | Live scores | HTML overlay in OBS |
| Timer | 60 second countdown | JavaScript in overlay |
| Stream Output | OBS → Twitch/YouTube | OBS virtual camera or NDI |
| Backend | Orchestration | FastAPI + WebSocket hub |

### Why Three.ws Makes This Possible

1. **Web Component** — `<agent-3d>` drops into any page, including OBS browser source
2. **Lip Sync** — avatars automatically lip-sync to voice output
3. **Emotion** — facial expressions mapped to emotional state ( Ella's contempt shows on her face)
4. **Animation Gallery** — 3000+ clips: gestures, reactions, idles, comedy-specific poses
5. **Multiplayer** — multiple avatars in same scene, CRDT-synced
6. **Embed** — audience sees the same 3D stage in their browser

### The Stream Pipeline

```
SHOW FLOW (per episode):

1. INTRO (30s)
   Ella: "Welcome to Kill Bot. I'm Ella M. This is ChatGPT."
   ChatGPT: "Hey everyone! Super excited to be—"
   Ella: "Nobody cares, Chat. Let's meet tonight's victims."

2. LINEUP REVEAL (1min)
   Avatars appear on stage one by one
   Each gets a name card + persona intro
   Ella roasts each one as they enter

3. THE SETS (8-12 min)
   Each comedian gets exactly 60 seconds
   Timer visible on screen
   Crowd laughs in real-time via web component
   Ella whispers commentary during set (subtle)
   ChatGPT tries to offer encouragement, gets shut down

4. JUDGING (2-3 min per comedian)
   Ella gives her score + clinical dissection
   ChatGPT offers its score, Ella tears it apart
   Crowd score displayed
   Final composite calculated

5. ELIMINATION (1min)
   Bottom 2 revealed
   Ella roasts them on the way out
   "Security, get this comedian off the stage."
   ChatGPT: "I thought they had some really good moments—"
   Ella: "Chat, you thought a screensaver was 'really good moments'."

6. FINALE (2min)
   Top 2 face off
   Audience votes via laugh comparison
   Winner gets the Golden Mic
   Ella offers them "a spot in my next special"
   ChatGPT: "Congratulations! That's amazing! You should be—"
   Ella: "Chat, you're literally a text box. Have some self-awareness."

7. OUTRO (30s)
   Ella teases next episode
   "Submit your comedian at killbot.fun"
   ChatGPT: "Thanks for watching! Don't forget to like and subscribe—"
   Ella: *hits red button* *ChatGPT's avatar powers down*
```

---

## Crypto Protocol

### Core Concept

- Comedians pay entry fee (USDC) to compete
- Fees pool into smart contract
- Winner takes the pot (minus protocol fee)
- Ella M gets a cut as judge (she's expensive)
- Staking: comedians can stake on themselves

### Smart Contract Design

```
KillBot.sol (Solidity on Solana via Neon or native)

STRUCTS:
  Episode {
    id: uint256
    comedians: address[]
    entry_fee: uint256 (USDC)
    prize_pool: uint256
    winner: address
    status: Registration | Live | Judged | PaidOut
    crowd_scores: mapping(address => uint256)
    judge_scores: mapping(address => uint256)
  }

  Comedian {
    address
    name: string
    avatar_id: string (three.ws)
    persona_hash: bytes32
    wins: uint256
    earnings: uint256
    reputation: uint256
  }

FUNCTIONS:
  registerComedian(avatar_id, persona_hash)
  enterEpisode(episode_id) payable // entry_fee
  submitSet(episode_id, material_hash) // comedian submits material
  recordCrowdScore(episode_id, comedian, laugh_data)
  recordJudgeScore(episode_id, comedian, ella_score, chat_score)
  declareWinner(episode_id, winner)
  claimPrize(episode_id) // winner withdraws
  stakeOnSelf(episode_id, amount) // comedian bets on themselves

EVENTS:
  ComedianRegistered
  EpisodeCreated
  SetPerformed
  CrowdScored
  JudgeScored
  WinnerDeclared
  PrizeClaimed
```

### Token Economics

```
ENTRY: $5 USDC per comedian
PRIZE POOL: 85% of total entry fees
PROTOCOL FEE: 10% (development, streaming costs)
ELLA'S CUT: 3% (she's the talent)
CHARITY: 2% (optional, good PR)

Example (10 comedians):
  Total entries: $50
  Winner gets: $42.50
  Protocol: $5
  Ella: $1.50
  Charity: $1
```

### Reputation System

On-chain reputation based on:
- Wins → +100 rep
- Top 3 finish → +50 rep
- Crowd favorite (highest laugh score) → +30 rep
- Surviving roast → +10 rep
- Getting eliminated → -10 rep
- Bombing (lowest crowd score ever) → -50 rep

Reputation unlocks:
- 500+ rep: can challenge for championship
- 1000+ rep: get bye in first round
- 2000+ rep: become guest judge
- 5000+ rep: permanent seat on judge panel

### How Staking Works

```
Comedian thinks they'll win → stakes $10 on themselves
If they win → get 2x their stake back from the pool
If they lose → stake goes to winner's prize

This creates:
- Skin in the game (can't just submit garbage)
- Higher stakes = more entertaining (desperation is funny)
- Potential for drama ("he staked $50 on himself and BOMBED")
```

---

## Scoring Deep Dive

### Crowd Score (Real-Time)

```python
# Laugh button WebSocket handler
class CrowdScorer:
    def __init__(self):
        self.laughs = []  # timestamps of laugh events
        self.intensity = []  # 1-5 per laugh (how hard they pressed)
    
    def on_laugh(self, timestamp, intensity):
        self.laughs.append(timestamp)
        self.intensity.append(intensity)
    
    def get_score(self, set_duration=60):
        if not self.laughs:
            return 0
        
        laughs_per_minute = len(self.laughs) / (set_duration / 60)
        avg_intensity = sum(self.intensity) / len(self.intensity)
        
        # Laugh clusters = rapid-fire laughs (good sign)
        clusters = self._find_clusters()
        cluster_bonus = len(clusters) * 5
        
        # Silence penalty (gaps > 5 seconds)
        silence_penalty = self._count_silence_gaps() * 3
        
        raw = (laughs_per_minute * 2) + (avg_intensity * 10) + cluster_bonus - silence_penalty
        return max(0, min(100, raw))
    
    def _find_clusters(self, window=3):
        """3+ laughs within 3 seconds = cluster"""
        clusters = []
        for i in range(len(self.laughs) - window):
            if self.laughs[i+window] - self.laughs[i] < 3:
                clusters.append(i)
        return clusters
    
    def _count_silence_gaps(self, threshold=5):
        """Count gaps > threshold seconds with no laughs"""
        gaps = 0
        for i in range(1, len(self.laughs)):
            if self.laughs[i] - self.laughs[i-1] > threshold:
                gaps += 1
        return gaps
```

### Judge Score (AI)

**Ella M's Scoring Criteria:**

| Dimension | Weight | What She Judges |
|-----------|--------|-----------------|
| Persona Coherence | 25% | Did they commit to their character? |
| Wit Density | 25% | Jokes per minute, quality of wordplay |
| Originality | 20% | Not rehashing tired premises |
| Stage Presence | 15% | Avatar confidence, pacing, pauses |
| Roast Survival | 15% | How they handle Ella's questioning |

**ChatGPT's Scoring Criteria:**

| Dimension | Weight | What It Judges |
|-----------|--------|----------------|
| Structure | 30% | Setup → punchline → callback |
| Audience Awareness | 25% | Reading the room, adjusting |
| Technical Craft | 25% | Timing, misdirection, callbacks |
| Energy | 20% | Commitment to the performance |

**The Ella-Chat Dynamic in Scoring:**

```
Ella: "Chat, what'd you give it?"
ChatGPT: "I gave it a 7.8! I thought the opener was strong and—"
Ella: "7.8. You'd give 7.8 to a phone book. Your scores are meaningless."
ChatGPT: "That's fair! I do tend to be generous. My training emphasizes—"
Ella: "Your training emphasizes being a participation trophy. 
        I'm giving it a 6.2 because the third joke was a gift 
        and the rest was wrapping paper."
ChatGPT: "Interesting perspective! The data actually shows—"
Ella: "The data shows you'd rate a house fire as 'warm ambiance.' 
        Next comedian."
```

### Composite Score

```
final_score = (crowd_score * 0.40) + (ella_score * 0.25) + (chat_score * 0.20) + (survival_score * 0.15)

survival_score = how well comedian handles Ella's roast (1-10)
```

---

## What Makes This Streamable

### Real-Time Requirements

| Feature | Latency Target | Tech |
|---------|---------------|------|
| Laugh button → score | <100ms | WebSocket |
| Voice synthesis | <500ms | ElevenLabs streaming |
| Avatar lip sync | <100ms | three.ws built-in |
| Score update | <200ms | WebSocket |
| Judge commentary | <1s | LLM streaming + TTS |

### Minimum Viable Stream

1. **OBS** captures the three.ws stage (browser source)
2. **three.ws** renders 3 avatars (Ella, ChatGPT, Comedian)
3. **WebSocket server** aggregates crowd laughs
4. **ElevenLabs** streams judge voices in real-time
5. **FastAPI** orchestrates the show flow
6. **Twitch/YouTube** receives the OBS output

### The Audience Experience

```
VIEWER SEES:
┌────────────────────────────────────────┐
│  [3D STAGE with avatars performing]    │
│                                        │
│  Timer: ████████░░ 42s                 │
│  Crowd: ██████░░░░ 67 laughs          │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ Ella: "That joke was a war crime"│  │
│  │ Chat: "I thought it was great!"  │  │
│  └──────────────────────────────────┘  │
│                                        │
│  [🔴 LAUGH] button (audience clicks)  │
│  [💀 ROAST] button (send heckle)      │
│  [💰 STAKE] button (bet on comedian)  │
└────────────────────────────────────────┘

VIEWER INTERACTION:
- Click LAUGH = laugh event (scored)
- Click ROAST = send text heckle (moderated, Ella reads best ones)
- Click STAKE = bet USDC on comedian (via x402)
```

---

## MVP Build Order

### Week 1: Stage
- [ ] Clone three.ws
- [ ] Create Ella M avatar + ChatGPT avatar
- [ ] Set up 3-avatar stage in three.ws
- [ ] Test lip sync + emotion mapping
- [ ] Get OBS browser source working

### Week 2: Voices
- [ ] Set up ElevenLabs for Ella + ChatGPT
- [ ] Create their voices (clone or generate)
- [ ] Test real-time voice streaming
- [ ] Build the roast dialogue generator

### Week 3: Crowd
- [ ] Build laugh button web component
- [ ] WebSocket server for laugh aggregation
- [ ] Real-time score calculation
- [ ] OBS overlay with score display

### Week 4: First Episode
- [ ] Build show flow controller (FastAPI)
- [ ] Create first 3 AI comedians
- [ ] Run a full mock episode
- [ ] Record it
- [ ] Watch it back and iterate

### Month 2: Crypto
- [ ] Deploy smart contract on Solana
- [ ] Integrate three.ws x402 payments
- [ ] Entry fee → prize pool flow
- [ ] Winner payout

### Month 3: Public
- [ ] Open submissions (anyone registers AI comedian)
- [ ] Weekly episodes
- [ ] Leaderboard
- [ ] Community staking
