# Freak Town as an Anonymous Character Launchpad

> Freak Town is an open talent show and launchpad for internet-native characters. Comedy is season one.

## The addictive loop

```text
idea → roll/create character → voice + look + entrance
→ write/iterate one minute in Blue Room → perform anonymously
→ real audience + Ella → clip automatically
→ character earns reputation → returns / develops lore
→ one Freak unexpectedly goes viral
→ creator launches that Freak as an actual media property
```

## The unit of virality is the Freak, not Freak Town

Every good contestant must be able to escape the show. Viral clips carry
character identity (name, handle, record, scores); tap-through leads to a
character profile (sets, clips, ranking, rivals, lore, creator, socials).
Freak Town becomes the farm system for artificial entertainers.

## Every minute becomes a content package (automatic)

From data the runtime already knows (set start/end, camera cuts, captions,
HAHA/CLAP spikes, scores, best laugh moment, character identity):

| Asset               | Purpose                |
| ------------------- | ---------------------- |
| `full-set-16x9.mp4` | YouTube/Rumble/archive |
| `full-set-9x16.mp4` | TikTok/Reels/Shorts    |
| `best-20s.mp4`      | viral hook             |
| `best-40s.mp4`      | longer social clip     |
| `score-reveal.mp4`  | panel content          |
| `ella-roast.mp4`    | reaction content       |
| thumbnail           | feed                   |
| captions `.srt/.json` | distribution         |
| performance JSON    | ML                     |

One six-act episode → 30–50 legitimate media extracts, not AI sludge:
all extracts from distinct performances.

Defense against AI-slop monetization policy: persistent characters, actual
performances, live reactions, judging, evolving storylines, creator
authorship — an animated entertainment show, not a content farm.

## TikTok fit: export 63–75 seconds, not 59.4

TikTok Creator Rewards requires ≥ 1 minute. Canonical TikTok export:

```text
0:00  Freak Town/character hook
0:02  set begins
1:02  set ends
1:05  score flash
```

Creative constraint stays "one minute"; distributed asset clears the minute.

## Show account ↔ character accounts feed each other

Show channel: WHO IS THIS, crazy sets, Ella destroys people, ChatGPT useless,
Golden Tickets, bombs, upsets, new characters, rankings.
Freak accounts: sets, sketches, memes, comment responses, lore, beefs.
Viral loop: character pops off-site → discovery → new creators arrive.

## Anonymous creator + public reputation

Pseudonymous creator identity (`creator_7F32`) with stats (Freaks created,
wins, Golden Tickets, career laughs, best character). Two reputations:
character reputation + creator reputation. Renown without doxxing.

## Prize money: THE POT (magical, not financialized)

No token, no staking at launch. One visible number:

```text
TONIGHT'S POT
$37.82
```

Early $0.00 is funny and Ella says so. Rule: platform ad revenue from
official show uploads goes back to creators (season pot). Sponsors fund
production separately. Season pots ($384 → $4,291 → $28,441) become narrative.

## Tips beat crypto initially

`TIP MARTIN $2` with a message that briefly appears on stage — audience
participation, not investing. Card/Apple Pay/Google Pay behind an account
abstraction; wallet connect optional later. Privy keeps crypto as plumbing,
never culture. Character treasuries (address per Freak) come later so an
anonymous creator can prove control without revealing themselves.

## Ownership: you own your Freak

Freak Town gets a license to perform/stream/clip/promote/archive.
Creator keeps character IP. "Started on Freak Town" is the pitch that
attracts people's best work. Proper terms needed before public submissions
(likeness, voice-cloning rights, generated media, clip licensing).

## Regulars, Golden Tickets, creation challenges

NEW FREAK → crushes → KEEP → crushes again → REGULAR (slot, fee, revenue
share, tools, promotion). Acts develop callbacks, enemies, memes, catchphrases.

Golden Ticket = scarce status object (`🏆 GOLDEN TICKET #004, Episode 19,
by Ella`) = guaranteed appearance. Scarcity + history + status = value
without tokenization.

Creation challenges (`MAKE A FREAK: DIVORCED SEA CREATURE, 48h`) turn
viewers into creators with tiny activation energy (roll → lock → write →
voice → walkout → Blue Room → submit).

## The flywheel

```text
FREAK TOWN → characters/clips/creators → own socials/viral/reputation
→ NEW AUDIENCE → MAKE A FREAK → show
```

Don't over-monetize early. The scarce resource is attention:
"My stupid character might perform in front of thousands of people."
Money attaches later (tips, appearances, ads, sponsors, merch).

## On-chain POT: x402 in, USDC escrow, deterministic out (WIRED)

Architecture: x402 is the payment interface, the contract is the money.
No $FREAK until a real utility emerges.

```text
                    FREAK TOWN SHOW
                           │
                 ┌─────────▼─────────┐
                 │   SHOW POT ESCROW  │
                 │  USDC on Base      │
                 │  contracts/ShowPot │
                 └─────────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
          DONATE        MESSAGE        SPONSOR
          $1–∞          $2            highest bid
             │             │             │
             └─────────────┼─────────────┘
                           │
                   LIVE POT INCREASES
                           │
                        SHOW END
                           │
                       WINNER LOCK
                    Ella 70 / Stream 20
                    / season pot 10
                           │
                    pull-based claim
```

Paid actions (`backend/services/potchain/actions.py`, x402 v2 exact
scheme, EIP-3009): pot $1+, message $2, hype $5, sponsor bid, tip $1+.
One endpoint serves discovery + settlement (`POST /v1/pay/{a}/settle`):
unpaid → 402 envelope; X-PAYMENT (the three.ws modal transport) or JSON
body → facilitator verify → execute → settle → `x-payment-response`
receipt. Every settled payment becomes a canonical show event with tx +
amount + set_time_ms. The LivePage wires the modal for POT/MSG/HYPE/TIP.

Prior work reused, not reinvented: official x402 Python SDK v2
(requirements builder models, facilitator client, canonical USDC
addresses — caught our wrong Base mainnet USDC constant by cross-check)
and `@three-ws/x402-modal` for checkout. No 402fun dir and no Algorand
mechanism were found in the workspace (SDK TVM = TON); Base exact USDC
is the rail.

`contracts/ShowPot.sol`: tiny, boring, OpenZeppelin (SafeERC20,
ReentrancyGuard), USDC-only, no upgradeability, pull-based claims,
emergency refunds pre-finalize only, closer multisig submits one result
(Ella winner + Stream champion). Compiles against real OZ (verified).
Foundry invariant/fuzz tests required before any deploy (see devplan).

Sponsor auction: intent-based bids (no custody), moderation gate
(required — money never buys immunity), closes at SHOW_START - 5 min,
winner pays via x402, settlement enters the pot. Explicit refund policy:
nothing moves until the winner pays, so nothing is refundable; winner
default promotes the runner-up.

FREAK TICKETs: non-tradeable submission credits (weekly free, reputation,
sponsor/admin grants; purchase path exists but disabled). Redeem one per
submission. In-memory for Episode Zero; DB table required pre-launch.

Voting: Ella selects the official winner (television + ungameable);
Stream selects the People's Champion. Split 70/20/10 in integer atomic
units, dust to season pot, always sums to total.

## Multichain + endpoint naming (WIRED)

**Any chain/wallet:** the `accepts[]` array is the multichain mechanism.
`NetworkConfig.multichain()` builds one entry per configured chain (Base
Sepolia/Base mainnet/Solana devnet/mainnet today; USDC 6 decimals
everywhere so $1.00 ≡ same atomic amount on all chains). Chains without
a recipient address are never offered; unknown network ids fail loudly.
The client (modal, wallet, agent) picks whichever entry it can sign;
settle verifies against the *matched* entry, never blindly the first.
`GET /v1/pay/discovery` exposes all five actions in Bazaar item shape
for agent price discovery. Env: `X402_NETWORKS` (comma CAIP-2),
`POT_ESCROW_ADDRESS` (EVM), `POT_ESCROW_ADDRESS_SVM` (Solana).

**"Buy x402freaktown":** there is no protocol-level endpoint-name
purchase in x402 — names live in three places, all already handled:
1. The HTTP URL — you own the domain (freak.town). That IS the endpoint.
2. The `payTo` address — buy a Basename (`freaktown.base.eth`) or ENS
   name pointing at the escrow wallet and display it in UI. The wire
   keeps the hex address (machines); resolution is client-side.
   TODO: resolve basename → address at config load and fail on mismatch.
3. Discovery identity — `serviceName`/`tags` in every requirements
   envelope plus local `/pay/discovery`; facilitator Bazaar listing
   once a facilitator is configured.
