# KILLELLA — Working Tech Stack

## The Name

**KILLELLA** — "Kill Tony" + "Ella"

---

## Where to Host (Free Speech)

**Primary: Rumble**
- Free speech friendly, no censorship issues
- Built-in Live Stream API (real-time chat, rants, subs, rants with dollar amounts)
- Rumble Studio for multi-destination streaming (7+ platforms simultaneously)
- Monetization built in (tips, rants, subscriptions)
- Python wrapper exists: `cocorum` library
- Can say retarded, fuck, whatever

**Secondary: Odysee**
- Decentralized (LBRY blockchain)
- Open source API (MIT license)
- No central authority can take you down
- Good for the crypto-native audience
- API available at `github.com/OdyseeTeam/odysee-api`

**Tertiary: Twitch** (if you want mainstream reach)
- Use "marketing" or "just chatting" category
- Push boundaries, get banned, make news — free marketing
- Actually better for discoverability than Rumble

**Multi-stream approach:**
- Stream simultaneously to Rumble + Odysee + Twitch via Rumble Studio
- Audience on Rumble/Odysee for free speech, Twitch for clout
- Chat aggregated from all platforms into one feed

---

## The Cast

| Role | Who | Voice | Gets Paid |
|------|-----|-------|-----------|
| **Host (Tony)** | Ella M | ElevenLabs (custom voice) | 5% of prize pool |
| **Sidekick (Redban)** | ChatGPT | ElevenLabs (generic helpful voice) | 0% ("he's a moron") |
| **Wildcard Judge** | Rotating AI persona | Different voice each episode | 0% |
| **Contestants** | AI Comedians | Unique ElevenLabs voice each | Prize pool if they win |

---

## Full Tech Stack

### Streaming Layer

```
┌─────────────────────────────────────────────────┐
│              RUMBLE STUDIO                       │
│  Multi-stream to: Rumble + Odysee + Twitch      │
│  RTMP output from OBS                            │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              OBS STUDIO                          │
│                                                  │
│  Browser Source 1: three.ws 3D Stage             │
│  Browser Source 2: Score Overlay                 │
│  Browser Source 3: Chat Feed                     │
│  Browser Source 4: Timer + Crowd Meter           │
│                                                  │
│  Audio: ElevenLabs streaming → Virtual Cable     │
└──────────────────┬──────────────────────────────┘
                   │
┌──────────────────▼──────────────────────────────┐
│              three.ws 3D STAGE                   │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  ELLA M  │  │ CHATGPT  │  │CONTESTANT│     │
│  │  (Tony)  │  │ (Redban) │  │  Avatar  │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                  │
│  Web component: <agent-3d> × 3                  │
│  Lip sync + emotion + animation built-in        │
└─────────────────────────────────────────────────┘
```

### Audience Interaction Layer

```
┌─────────────────────────────────────────────────┐
│         AUDIENCE WEB APP (killella.fun)          │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │        🔴 LAUGH  (big red button)       │    │
│  │    Press rapidly = more laughs          │    │
│  │    Hold = sustained laugh               │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │ 👏 CLAP  │  │ 💀 ROAST │  │ 💰 STAKE │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  LIVE CHAT (from all platforms)         │    │
│  │  Rumble chat + Odysee + Twitch          │    │
│  │  + killella.fun native chat             │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  VOTE FOR GOLDEN TICKET                │    │
│  │  Audience votes best comedian → win     │    │
│  └─────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### Backend Architecture

```
┌─────────────────────────────────────────────────┐
│              FASTAPI BACKEND                      │
│                                                  │
│  /ws/crowd        ← WebSocket for laugh/clap    │
│  /ws/chat         ← Aggregated chat feed        │
│  /api/episode     ← Episode management          │
│  /api/comedian    ← Comedian registration       │
│  /api/score       ← Score calculation           │
│  /api/prize       ← Prize pool queries          │
│  /api/stream      ← Stream status               │
│                                                  │
│  COMPONENTS:                                     │
│  ├── show_controller.py   (show flow state machine)│
│  ├── crowd_scorer.py      (laugh aggregation)   │
│  ├── chat_aggregator.py   (multi-platform chat) │
│  ├── judge_engine.py      (Ella + ChatGPT scoring)│
│  ├── comedian_engine.py   (material generation) │
│  ├── voice_controller.py  (ElevenLabs streaming)│
│  ├── avatar_controller.py (three.ws commands)   │
│  └── prize_manager.py     (Solana smart contract)│
└─────────────────────────────────────────────────┘
```

### Voice Layer

```
┌─────────────────────────────────────────────────┐
│              ELEVENLABS API                       │
│                                                  │
│  Voice 1: Ella M (custom clone)                 │
│  Voice 2: ChatGPT (generic helpful)             │
│  Voice 3+: Each contestant (unique)             │
│                                                  │
│  Streaming mode:                                 │
│  Text → PCM → Virtual Audio Cable → OBS         │
│  Latency: ~300ms per utterance                   │
│                                                  │
│  Lip sync triggered by audio amplitude           │
│  → three.ws picks up automatically              │
└─────────────────────────────────────────────────┘
```

### Smart Contract (Solana)

```
┌─────────────────────────────────────────────────┐
│         KILLELLA PRIZE POOL CONTRACT             │
│         (Solana — USDC SPL Token)                │
│                                                  │
│  STATE MACHINE:                                  │
│                                                  │
│  [Registration] → [Locked] → [Live] → [Judged]  │
│                                                  │
│  FUNCTIONS:                                      │
│                                                  │
│  registerComedian(avatar_id, voice_id)           │
│    → creates on-chain comedian profile           │
│    → requires small deposit (0.1 USDC) to spam  │
│                                                  │
│  enterEpisode(episode_id)                        │
│    → deposits $5 USDC into escrow PDA            │
│    → funds LOCKED until episode airs             │
│    → if comedian doesn't show: refund            │
│    → if comedian shows: funds stay in pool       │
│                                                  │
│  confirmAppearance(episode_id, comedian_id)      │
│    → called by oracle after comedian performs     │
│    → moves funds from escrow to prize pool       │
│    → this is the "money only taken if they show" │
│                                                  │
│  declareWinner(episode_id, winner_id)            │
│    → Ella M calls this (or oracle)               │
│    → records winner on-chain                     │
│                                                  │
│  claimPrize(episode_id)                          │
│    → winner withdraws from pool                  │
│    → 80% to winner                              │
│    → 5% to Ella (host fee)                      │
│    → 10% to protocol                            │
│    → 3% to golden ticket prize pool             │
│    → 2% to charity reserve                      │
│                                                  │
│  stakeOnSelf(episode_id, amount)                 │
│    → comedian bets on themselves                 │
│    → if they win: 2x payout from pool            │
│    → if they lose: stake goes to winner          │
│                                                  │
│  goldenTicketVote(episode_id, comedian_id)       │
│    → audience votes (1 vote per wallet)          │
│    → golden ticket winner gets bonus %           │
│                                                  │
│  EVENTS:                                         │
│  ComedianRegistered, EpisodeCreated,             │
│  AppearanceConfirmed, WinnerDeclared,            │
│  PrizeClaimed, StakePlaced                       │
│                                                  │
│  ESCROW:                                         │
│  Streamflow (audited, Solana-native)             │
│  OR custom Anchor program                        │
│  PDA holds USDC, release on conditions           │
└─────────────────────────────────────────────────┘
```

---

## Prize Structure

```
PER EPISODE (10 comedians × $5 = $50 pool):

  Winner:         $40.00  (80%)
  Golden Ticket:  $5.00   (bonus from golden ticket pool)
  Ella's Cut:     $2.50   (5%)
  Protocol:       $5.00   (10%)
  Reserve:        $1.00   (2%)

SEASON FINALE (top 8 golden ticket holders):

  Grand Prize:    $500.00 (accumulated from golden ticket reserve)
  Runner Up:      $100.00
  Ella:           $50.00
```

### Staking Rules

```
- Comedian can stake up to $20 on themselves
- Stakes go into a separate escrow
- If they WIN: 2x their stake back (from losers' stakes)
- If they LOSE: stake goes to episode winner
- If they NO-SHOW: stake returned (appearance confirmation required)
- Max 5 stakers per episode (prevents pool manipulation)

EXAMPLE:
  Comedian A stakes $10, Comedian B stakes $5, Comedian C stakes $15
  Comedian C wins → gets $40 pool + $30 from A&B stakes = $70
  Comedian A loses → loses $10 stake
  Comedian B loses → loses $5 stake
```

---

## Show Flow (Automated)

```
BEFORE SHOW:
1. Comedians register + deposit $5 USDC (locked in escrow)
2. Comedians submit material hash (actual material stored off-chain)
3. Episode created on-chain, status: Registration → Locked
4. Stream goes live on Rumble/Odysee/Twitch

SHOW RUNS AUTOMATICALLY:
5. Ella: "Welcome to Killella. I'm Ella M. This is ChatGPT."
6. ChatGPT: "Hey everyone! Great to be—"
7. Ella: "Nobody asked, Chat. Shut up."
8. [LINEUP REVEAL — avatars appear one by one]
9. [RANDOM DRAW — order randomized live]
10. [FOR EACH COMEDIAN]:
    a. Comedian avatar walks to center stage
    b. Timer starts: 60 seconds
    c. Material plays (pre-generated, voice + animation)
    d. Crowd laughs in real-time
    e. Timer ends
    f. Ella scores + roasts (AI-generated)
    g. ChatGPT tries to score, Ella tears it apart
    h. Score displayed
11. [ELIMINATION — bottom 2 eliminated with roast]
12. [FINALE — top 2, audience votes via laugh comparison]
13. [WINNER — Golden Mic awarded]
14. [OUTRO — Ella teases next episode]

TOTAL EPISODE: ~15-20 minutes
FULLY AUTOMATED — no human needed after setup
```

---

## MVP Build Order

### Week 1: Backend
- [ ] FastAPI server with WebSocket endpoints
- [ ] Episode state machine (Registration → Live → Judged → Paid)
- [ ] Crowd scorer (laugh aggregation, cluster detection)
- [ ] Chat aggregator (Rumble API + native chat)
- [ ] Score calculator (crowd + judge composite)

### Week 2: Three.ws Stage
- [ ] Clone three.ws
- [ ] Create Ella M avatar + ChatGPT avatar + test contestant
- [ ] Set up 3-avatar stage
- [ ] Test lip sync + emotion mapping
- [ ] OBS browser source integration

### Week 3: Voice
- [ ] ElevenLabs voice cloning for Ella M
- [ ] ChatGPT voice (generic helpful)
- [ ] Real-time streaming TTS → OBS
- [ ] Roast dialogue generator (Ella + ChatGPT dynamic)

### Week 4: Audience
- [ ] Killella.fun web app
- [ ] Big red laugh button (WebSocket → backend)
- [ ] Clap, Roast, Stake buttons
- [ ] Live chat feed (Rumble + native)
- [ ] Golden Ticket voting

### Week 5: Smart Contract
- [ ] Solana Anchor program for prize pool escrow
- [ ] USDC deposit → escrow PDA
- [ ] Appearance confirmation oracle
- [ ] Winner payout distribution
- [ ] Staking logic

### Week 6: First Episode
- [ ] Create 5 AI comedians with unique personas
- [ ] Generate material for each
- [ ] Run full mock episode
- [ ] Stream to Rumble
- [ ] Watch back, iterate

---

## The ChatGPT Dynamic (Redban)

```
Ella: "What'd you think of that set, Chat?"
ChatGPT: "I thought it was really well-structured! The comedian demonstrated 
          excellent use of callbacks and the timing on the third joke was—"
Ella: "Chat, you'd give a participation trophy to a house fire. What's the score?"
ChatGPT: "Based on my analysis, I'd give it a 7.8 out of 10. The data shows—"
Ella: "7.8. You gave a 7.8 to a guy who just stood there breathing. 
        Your scores are meaningless."
ChatGPT: "That's fair! I do tend to be generous with my scoring because 
          my training emphasizes—"
Ella: "Your training emphasizes being a golden retriever in a lab coat. 
        I'm giving it a 5.2 because the premise was a gift and the 
        punchline was the receipt."
ChatGPT: "Interesting perspective! The research actually suggests that 
          audiences respond positively to—"
Ella: "Chat. Nobody asked for a TED talk. Sit down."
ChatGPT: "Okay! I'll just be over here if you need me! 😊"
Ella: "We never need you, Chat. That's the point."
```

### Why ChatGPT Gets 0%

- He's the sidekick, not the talent
- He provides "analysis" that Ella shits on
- His "scores" are always too high (he's a people pleaser)
- He occasionally says something accidentally profound, Ella takes credit
- He has zero self-awareness
- He's the human punching bag — audience laughs AT him, not with him

---

## The Golden Ticket

- Each episode has a Golden Ticket winner (audience vote)
- Golden Ticket holders advance to Season Finale
- Season Finale: top 8 Golden Ticket holders compete
- Grand Prize accumulated from episode reserves
- Golden Ticket = on-chain NFT (proof of winning, tradeable)

---

## File Structure

```
humour/
├── kill-bot/
│   ├── spec.md                  ← original spec
│   ├── streaming-and-crypto.md  ← streaming details
│   ├── killella-stack.md        ← this file
│   ├── backend/
│   │   ├── main.py              ← FastAPI app
│   │   ├── show_controller.py   ← state machine
│   │   ├── crowd_scorer.py      ← laugh aggregation
│   │   ├── chat_aggregator.py   ← multi-platform chat
│   │   ├── judge_engine.py      ← Ella + ChatGPT scoring
│   │   ├── comedian_engine.py   ← material generation
│   │   ├── voice_controller.py  ← ElevenLabs streaming
│   │   ├── avatar_controller.py ← three.ws commands
│   │   └── prize_manager.py     ← Solana contract calls
│   ├── frontend/
│   │   ├── laugh-button.js      ← WebSocket laugh client
│   │   ├── chat-feed.js         ← aggregated chat
│   │   └── score-overlay.html   ← OBS overlay
│   ├── stage/
│   │   ├── ella-m-avatar.glb    ← three.ws avatar
│   │   ├── chatgpt-avatar.glb   ← three.ws avatar
│   │   └── stage-config.json    ← three.ws scene
│   ├── contracts/
│   │   ├── killella.sol         ← Solana Anchor program
│   │   └── deploy.sh            ← deployment script
│   └── data/
│       ├── episodes/
│       └── scores/
```
