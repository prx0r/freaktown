# Freak Town party games: inventory

Repo `prx0r/freaktown`. Base: `main` @ `c3d2f4e`. Fix branch: `party-games-playable`.
Line numbers below refer to `party.py` on `party-games-playable`.

## How every party.py game works (shared plumbing)

- **One server, two screens.** The big screen is `/party/<code>/stage`; each phone is `/party/<code>/play`. The server is Flask (`party_bp`, registered in `app.py`). There are no WebSockets: the stage polls `GET /party/<code>/stream?once=1` (SSE also works), and phones poll `GET /party/<code>/view?seat_token=…` and send `POST /party/<code>/input`.
- **Create:** `/play` lists every mode with a CREATE + HOST button. You can also call `POST /party/create`, which returns `{code, host_token}`. The host token lives in the stage tab's localStorage. `?host=<token>` now works too.
- **Join:** a phone opens `/join/<code>` (QR on the stage) and calls `POST /party/<code>/join {name, freak}`, which returns a `seat_token`. Seats are capped at 8. A late joiner (mid-game) or anyone after `lock` becomes **audience** (a 😂 button). Rejoin: `POST join {seat_token}` returns the same seat, including after `leave`.
- **Host commands:** `POST /party/<code>/host {host_token, cmd}`.
  - `lock`, `unlock`
  - `start {mode | pack, rounds?, target?, deck?}`. Also used for play-again; it resets scores.
  - `advance`
  - `end`
  - `lobby` (new: back to the lobby, scores reset, room unlocked)
  - `bots {n}`: free deck bots, now in every mode
  - `reject {player_id}` (roast moderation)
- **Leave (new):** `POST /party/<code>/leave {seat_token}`. In the lobby the seat is freed. Mid-game the seat is kept but nobody waits on it, and the same token can rejoin.
- **Timers:** enforced lazily on the next `/view`, `/input`, `/host` or (new) `/stream` request. Collecting phases last 90 s, voting/judging 60 s, and freaktionary drawing 90 s. **New:** a scored or reveal screen holds for `SCORED_HOLD = 12 s` and then moves on by itself, so a room keeps going when the host tab closes.
- **Persistence:** rooms are written to `party_rooms.json` after every non-high-frequency event, so they survive a restart. `party_records.json` holds cross-night wins and head-to-head "lore". Rooms idle for more than 24 h are now pruned.
- **TTS/LLM:** no party.py game calls an LLM. All prompts and bots are fixed decks, so they cost nothing. Roast Relay tries a free edge-tts read of the assembled set (`generation.ready`). That is best-effort, and `PARTY_TTS=0` turns it off.

## The games

| # | Game | Where it lives | Players | Rounds / phases | Scoring |
|---|---|---|---|---|---|
| 1 | **Freaktionary** (draw & guess, "MQ") | `party.py` `_mq_*` (L324–), mode `freaktionary` | 2–8 (bots OK) | One turn at the pen per player (default rounds = players). Each turn: `drawing` (90 s; the drawer sees the secret word, everyone else guesses), then `revealed` (word shown, 12 s hold), then the next drawer. Ends with `game.done`. | Correct guesser +2, drawer +1. Nobody gets it: 0. Guesses ignore case and punctuation. |
| 2 | **Roast Relay** ("RR", one line each) | `party.py` `_rr_*` (L474–), mode `roast-relay` | 3–8 (bots OK) | Default 3 rounds. `collecting` (90 s, one roast of the target each; the host can `reject` a line), then `voting` (60 s, authors hidden, no self-votes), then `scored` (12 s). Optional free TTS of the set. | Most-voted roast +3. |
| 3 | **Freeze Night** (improv evening, "FZ") | `party.py` `_fz_*` (L704–), mode `freeze-night`; content spec `game-packs/freeze-night-v1.freak-game.json` | 3–8 (bots OK; pack JSON says 4–8) | Fixed playlist `FZ_ROUNDS` of 7 rounds: scene1-ending, scene1-walkin, **ritual-halftime** (a victim; the others write `LINE // MANNER`; the longest line becomes the spotlight; then `passfail` and `author` guess), scene2-object, scene2-ending, **wheel-of-shame** (the lowest scorer spins; `verdict` served or double, up to 2 respins), **last-lash** (stack up to 3 votes, self allowed). Ends with `night.done`. | Prompt rounds: share of a 100 pool by vote %, +25 for a unanimous sweep, ×1.5 for a declared `callback:<event>`. Ritual: victim gets passes/others × 100; correct author guess +10; spotlight author +10 (+20 if nobody guessed). Wheel: served +2, doubled −2. Last-lash pool 300. |
| 4–14 | **Quip Clash** ("QC"): one engine, 11 decks | `party.py` `_qc_*` (L1394–), modes `quip-<deck>` | 2–8 (bots OK) | Default 3 rounds. `collecting` (90 s), then `voting` (60 s), then `scored` (12 s). | normal: vote % of 100, +25 sweep |
| | – quip-endings · FUNNIER ENDING | | | | normal |
| | – quip-walkins · WHO WALKS IN | | | | normal |
| | – quip-objects · POCKET OBJECT | | | | normal |
| | – quip-monologues · INTERNAL MONOLOGUE | | | | normal |
| | – quip-dubs · DUB THE CLIP | | | | normal |
| | – quip-eulogies · EULOGY FOR A THING | | | | normal |
| | – quip-lyrics · FINISH THE LYRIC | | | | normal |
| | – quip-nonsense · COURT OF NONSENSE | | | | normal |
| | – quip-least-funny · LEAST FUNNY ANSWER | | | | inverted: fewest votes wins (zero votes counts now), ties split 100 |
| | – quip-wrong-answers · WRONG ANSWERS ONLY | | | | inverted |
| | – quip-lies · WOULD I LIE TO YOU | | | Entries carry a secret TRUE/LIE toggle, revealed only at scoring. | liar: each vote names a suspected lie. Liar +15 per fooled voter; a voter +10 per catch. |
| 15 | **Pack: FREAK NIGHT** (playlist) | `PACKS` (L1866) | 3–8 | freaktionary → roast-relay → freaktionary, `rounds_each` (default 2, or the host's rounds). Ends with `pack.done`. | Cumulative. |
| 16 | **Pack: QUICK FIRE** | `PACKS` | 3–8 | roast-relay only. | Cumulative. |
| 17 | **Poker seat** (UI-only, live stage) | `apps/live/src/pages/PlayPage.tsx` (`/play/:episodeId/seat/:n`), dealer `packages/stage-runtime/src/sets/poker/PokerDealer.ts` | 1 human + bots | Hold'em hand: deal, then turns (fold/check/call/raise), then board, then showdown. Driven from `/control`. | Chip stacks. |

### Branch-only games (not on main; PR #7 `party-tnts`, also merged into `feature/mutuals-acting-party-smiles`, which has no PR)

All of these are TypeScript in `packages/party` plus `apps/live` pages. PR #7 is stacked on about 40k lines of other unmerged work (newsroom, sketch, LiveKit), so it can't be brought into a PR off main.

| Game | Where | How it plays |
|---|---|---|
| **Try Not To Smile (TNTS) vs agents** | `/tnts`, `packages/party/src/rules.ts` and `game.ts` | Webcam smile scored on the device (MediaPipe), 3 s neutral calibration, agents with taste models. Lives and strikes; a held smile above the threshold costs a life. |
| **Always-on rooms** (podcast "The Overthinkers", poker "Bluff Night", TNTS room, newsroom "Late Desk") | `/rooms`, `/rooms/:id`, `packages/party/src/rooms.ts` and `server/rooms-server.ts` | Agent residents keep the room going. A human takes a seat or queues for the next TNTS game. |
| **Write-a-minute** | `/minute`, `packages/party/src/minute.ts` | Premise, then an agent draft, then you edit text and delivery, then a stage preview, then the performance. |
| **Alien News** | `npm run party:alien-news` plus the newsroom render CLI | Two alien anchors in an invented language with subtitles (a rendered show, not interactive). |

### Not games

- `PlayPage.tsx` on main is only the poker seat. No React page exists for the party.py games (they are served as HTML from `party.py`).
- `HANDOVER-*.md` and `AGENTS.md` describe party.py as live traffic ("strangler, not rewrite"). This work keeps it in place.
