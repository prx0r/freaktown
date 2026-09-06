# Freak Town Vision: Show + Economic Layer for Fictional Performers

> **Freak Town is both a show and an economic layer for fictional performers.**

The character is the public identity, the human is the creator/author, and the wallet belongs to the creator.

On screen:

> **NO-NOSE NOLAN**
> Police sniffer dog without a sense of smell
> *created by @tomprior*
> `$184 earned`

The character feels real while the human gets authorship and status.

---

## Revenue: 5% is the core rule, but tips are not the main business

> **Creators keep 95%. Freak Town takes 5% for running the stage, payments, hosting, discovery and distribution.**

The 5% applies to **creator-directed economic activity**, not literally every dollar Freak Town earns.

| Source | Freak Town keeps | Creator gets |
|--------|---------------|--------------|
| Character tip ($10) | $0.50 | $9.50 |
| Ella/show tip | 100% | — |
| Opening sponsor slot | 100% | — |
| Character-commissioned sponsor | negotiated split | negotiated split |
| YouTube/Rumble ad revenue | platform revenue | — |

Tips alone won't finance the company. At 1,000 viewers, even if 3% tip an average $5, that's only $150 of creator GMV and **$7.50 to Freak Town at 5%**. The 5% aligns the ecosystem, but **advertising/sponsorship becomes the serious revenue engine**.

Rumble has already validated this ad product. Rumble Studio sells live host-read campaigns with on-screen advertiser/QR overlay, and campaigns can pay a flat amount or per live viewer. Freak Town can make that native to the fictional universe instead of reading generic ads.

---

## The sponsor product could be exceptionally good

Reserve a small number of **canonical inventory slots** in every episode.

Cold open:

> Ella: "Tonight's server bill is being paid by ElevenLabs. Apparently they heard this show and decided bad decisions needed better voices."

Logo appears physically behind her with `ELEVENLABS.COM/FREAK TOWN` or QR code.

Advertiser provides factual claims, prohibited phrases, CTA and required wording. Freak Town generates the actual read **before the show**, advertiser approves, final version is frozen. Don't let a live LLM freestyle regulated advertising.

### Native sponsor formats

| Inventory | Experience | Revenue owner |
|-----------|-----------|---------------|
| Opening sponsor | 20-30 sec Ella read | Freak Town |
| Set transition | 5-10 sec visual | Freak Town |
| Sponsored challenge | "The Stripe 10-Word Challenge" | Freak Town |
| Character sponsorship | Brand commissions/backs Nolan | Creator + Freak Town |
| Clip sponsor | Sponsor attached to viral short | Freak Town / creator |
| Show tip | Audience tips Ella/production | Freak Town |
| Character tip | Audience tips comedian | 95% creator / 5% Freak Town |

Do not build an ad exchange initially. Sell the first 20 campaigns manually. Learn what sponsors actually want, then encode into `SponsorCampaign`, `Placement`, `Creative`, `Bid`, `Impression`, `Conversion`.

Self-serve auction becomes valuable only once multiple advertisers are actually competing.

---

## Wallet UX: don't tell ordinary people they're creating wallets

Use **Privy + Solana + USDC**.

```text
Sign in with Google
        ↓
Freak Town account
        ↓
wallet silently provisioned
        ↓
$0.00 balance
```

Not:

```text
CREATE CRYPTO WALLET
WRITE DOWN THESE 12 WORDS
SELECT RPC
BUY SOL
```

Never show that unless the user opens advanced wallet settings.

### The tip transaction

No escrow contract needed for normal tips.

Someone presses **TIP NOLAN $5**:

```text
$4.75 USDC → creator
$0.25 USDC → Freak Town
```

Viewer approves once. Freak Town sponsors the tiny network fee (no SOL needed).

**Non-custodial platform economics.** You never receive Nolan's $4.75 and later "pay him out". It goes straight to him.

For fiat users, add Stripe Connect as the pure-fiat alternative. Connect explicitly supports routing money to creators while taking platform application fees.

```text
                TIP $5
                  │
         ┌────────┴────────┐
         ▼                 ▼
     PAY WITH           PAY WITH
     CARD/APPLE PAY      USDC
         │                 │
   Stripe Connect      Solana/Privy
         │                 │
         └────────┬────────┘
                  ▼
          CREATOR GETS 95%
          FREAK TOWN GETS 5%
```

The user shouldn't care which rail ran underneath.

---

## Make tipping part of the show

Tips become `ShowEvents`.

Someone sends Nolan $20 while he's bombing:

```text
💸 @james sent Nolan $20
"Don't give up on sniffing."
```

A little $20 animation appears beside him.

Ella sees it.

> "Somebody just paid you twenty dollars to keep going. That's the most devastating review you've had all night."

Now monetization creates content.

Someone tips Ella:

> **$50 TO ELLA**

Ella: "Correct decision."

Someone tips Chat:

> **$100 TO CHAT**

Ella: "What the fuck are you doing?"

**Money becomes another input into the improv environment.**

Moderate messages, rate-limit them, don't make tip size mechanically determine who wins.

---

## Character pages become economically meaningful

```text
NO-NOSE NOLAN

by @tomprior

[ avatar ]

Total earned        $1,843
Appearances          7
Best laugh           81%
Followers            12,481

ACTS
#7 Airport Security
#6 Tinder for Dogs
#5 Veterinary School
...

[ FOLLOW ] [ TIP $5 ]
```

And creator profile:

```text
@tomprior

CREATED

No-Nose Nolan
DivorceGPT
The Depressed Toaster
...
```

People become fans of:
1. Freak Town
2. Particular characters
3. Particular **creators**

The creator becomes analogous to an animator/writer/comic rolled together.

---

## The moat is not the LLM

Anyone can copy:

```text
LLM + TTS + 3D avatar + comedy prompt
```

That is essentially zero moat.

The moat is the accumulated graph:

```text
CREATORS
    ↓
CHARACTERS
    ↓
ACT VERSIONS
    ↓
APPEARANCES
    ↓
INTERACTIONS
    ↓
AUDIENCE
    ↓
FOLLOWERS
    ↓
EARNINGS
    ↓
CANON
```

If No-Nose Nolan has performed 40 times, has 300,000 followers, $42k lifetime earnings, recurring enemies, historical clips, a relationship with Ella and a creator with five other characters, **you cannot reproduce Nolan by copying his system prompt**.

Identity + history becomes an asset.

Beneath that you accumulate potentially even more valuable data:

```text
exact script
authorship provenance
character
voice
delivery
animation
model
latency
audience response by millisecond
Ella interview
live improvisation
revision history
creator patches
future performance
```

A proprietary dataset about what makes artificial/virtual performance entertaining.

### The four moats

| Moat | What it is |
|------|-----------|
| **Technical** | Performance data + generation provenance dataset |
| **Network** | All creators and characters |
| **Cultural** | Ella + the show's canon |
| **Distribution** | The clip machine |
| **Economic** | Creators actually earn money there |

---

## The technical architecture: the website itself runs the stage

Every audience browser receives the same `ShowEvents` that OBS receives.

```text
                    SHOW ENGINE
                         │
                         │ events
            ┌────────────┼────────────┐
            ▼            ▼            ▼
        OBS STAGE     TOM'S PHONE   JAMES' LAPTOP
        CLIENT        CLIENT        CLIENT
            │
            ▼
      Rumble/YouTube
```

OBS is **just another Freak Town client**.

If Nolan enters:

```json
{"type": "character.enter", "character": "no_nose_nolan"}
```

every browser renders Nolan locally.

If Nolan speaks:

```json
{"type": "speech.play", "asset": "...", "start_at": 1834237821}
```

every browser plays it.

### Benefits

- Audience on freak_town.com gets real-time stage events, synchronized laughs, instant tips, interactive buttons, selectable cameras, no livestream latency, no expensive video bandwidth
- OBS renders precisely the same scene and broadcasts to YouTube/Rumble for discovery
- Much more defensible than operating a normal livestream

---

## Cloudflare for the live layer

One **Durable Object per live episode**.

Cloudflare positions Durable Objects as a single coordination point for multiplayer/chat-style clients; one object can serve thousands of WebSockets, documented ceiling is 32,768 WebSockets per DO.

```text
Episode 42
     │
     ▼
┌──────────────────────────┐
│ EpisodeRoom DurableObject│
│                          │
│ phase                    │
│ current character        │
│ timer                    │
│ audience sockets         │
│ laugh aggregation        │
│ tip events               │
│ stage broadcasts         │
└────────────┬─────────────┘
             │
     2,000 browsers
```

Python backend remains the **production brain**: LLM, TTS, submissions, moderation, judging, Postgres, generation.

Cloudflare becomes the **live nervous system**.

---

## Canonical stack

| Layer | Choice |
|-------|--------|
| Consumer/creator app | Next.js + React + TypeScript |
| Stage | React Three Fiber + Three.js |
| Human avatars | `@pixiv/three-vrm` |
| Lip sync | `three-vrm-lip-sync` / custom WebAudio visemes |
| Non-human characters | curated GLB rigs + animation adapters |
| Stage state | Zustand |
| Realtime room | Cloudflare Durable Objects + WebSockets |
| Assets/audio | Cloudflare R2 |
| Core database | PostgreSQL |
| Backend/API | FastAPI + Pydantic + SQLAlchemy |
| Background work | Redis queue initially |
| TTS | edge-tts (MVP), ElevenLabs (production) |
| LLM | provider abstraction |
| Auth + crypto | Privy |
| Chain | Solana |
| Asset | USDC |
| RPC | Helius or equivalent |
| Fiat payments | Stripe Connect |
| Production stream | OBS |
| Distribution | Rumble Studio → Rumble + YouTube + others |

Cloudflare R2 charges no Internet egress — serving character/audio assets to many audience clients has no bandwidth bill.

`@pixiv/three-vrm` provides the VRM Three.js runtime. MIT `three-vrm-lip-sync` drives visemes from live or prerecorded browser audio.

For humanoid motions, Mixamo remains commercially usable and royalty-free. For non-humanoid (Nolan the dog), separate quadruped adapter.

---

## Body families for visual quality

Don't permit arbitrary models initially. Create **body families**:

```text
HUMANOID
DOG
CAT
ROBOT
CREATURE
OBJECT
```

Each family defines:

```text
idle
talk
walk_on
walk_off
look_left
look_right
laugh
angry
confused
celebrate
die/bomb
mouth_driver
```

Then skin them.

A dog creator doesn't need to animate a dog. They select "German Shepherd" and Freak Town already knows how that body acts.

Later user-generated GLB/VRM characters can be uploaded and validated against an animation contract.

---

## Stream monetization becomes additive

```text
                    FREAK TOWN REVENUE

        ┌──────────────────────────────────┐
        │                                  │
     OWN ECONOMY                      DISTRIBUTION
        │                                  │
 Creator tips → 5%                Rumble programmatic
 Sponsor inventory                YouTube advertising
 Show/Ella tips                   YouTube Supers
 Premium creator tools            Rumble tips
 Character marketplace            Platform programs
        │                                  │
        └────────────────┬─────────────────┘
                         │
                     FREAK TOWN
```

Platform ad revenue is a bonus. **Your valuable inventory is the inventory you own.**

---

## Keep character creation completely open

The headline:

> **PUT SOMETHING ON STAGE.**

Credits preserve exactly who made it:

```text
NO-NOSE NOLAN
created by @tomprior

Minute:
Written by @tomprior

Character:
@tomprior

Interview:
Freak Town AI

Voice:
Freak Town Voice #14
```

Or:

```text
DEATHBOT 9000
created by @alice

Minute:
100% autonomous

Brain:
Alice's custom agent

Model:
revealed after set
```

They coexist without the platform declaring one "purer."

---

## The thesis

> **A marketplace and live stage for synthetic characters, with comedy as the first killer format.**

Comedy gets people there. Characters, creator identities, canon, audience relationships and economics produce the moat.

The 95/5 direct creator economy + sponsor-funded show + locally rendered interactive stage is the structural version to build now. It gives revenue without pay-to-play, gives creators a real reason to keep making characters, and makes Freak Town materially better than simply posting an AI comedy video to YouTube.
