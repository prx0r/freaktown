# Party games playtest (2026-10-26)

Branch `party-games-playable` (one commit off `main` @ `c3d2f4e`), PR #15.

## Method

- **Server:** `PARTY_TTS=0 PORT=8090 python3 app.py`, the real Flask app with the FUNNIER skin. Python 3.12 on an aarch64 sandbox. Chromium 156 from Debian, because Playwright's arm64 download returns 403.
- **HTTP bot phones** (`botplay.py`): 3–4 clients per game. Each phone only GETs its own `/view` and acts on the components it is shown, the same way the phone page does: ready → draw/guess/write/vote/judge. A host polls `/stream` and advances on score screens. Every game is played to a winner, then play-again (1 round, scores reset), then `lobby`. Results: `test-output/botplay-1.txt` and `botplay-2.txt` (+ `.json`). **61/61 scenarios passed.**
- **Real UI** (`uiplay.py`, headless Chromium):
  - Clicks CREATE + HOST on `/play`.
  - 3 phones join through `/join/<code>` and tap I'M READY.
  - The stage sets rounds and clicks START.
  - Phones type, tap options and draw on the canvas with the mouse.
  - The stage clicks ADVANCE on score screens, then PLAY AGAIN, then LOBBY.
  - Stage and phone are screenshotted at every phase. No JS errors in any run.
- **UI edge cases** (`uiedge.py`): 9/9 passed.
- **Contract tests** (`tests/contract/test_party_games.py`, in the PR): 49 passed, in-process with a mocked clock.

## Per game

| Game | API bots | Real UI | Status | Bugs found → fixed |
|---|---|---|---|---|
| Freaktionary | 4 humans; 2 humans + 2 bots; play again; lobby ✔ | 3 phones, 3 rounds: draw, guess, reveal ×3, winner ✔ (`contact/freaktionary_contact.jpg`) | **fixed** | Never ended (no round limit). Reveal screen never showed (phase stayed `drawing`). "Solo: bots guess + draw" was advertised but bots weren't allowed. Guesses were case/punctuation-strict. No stage button to start it. |
| Roast Relay | 4 humans; 1 human + 2 bots ✔ | 3 phones, 2 rounds ✔ | **fixed** | Never ended. Timeout with no lines looped forever. Vote ids allowed a seat with no clip. No bots. No stage button. Edge-tts thread could write audio into a later round. |
| Freeze Night | 4 humans; 2 humans + 2 bots ✔ | 3 phones: all 7 rounds incl. ritual (write, pass/fail, author), wheel verdict, last-lash multi-vote ✔ | **fixed** | **Phones could not play the ritual or last-lash at all** (wrong `kind` / missing `choice`). Callback marker counted as an entry, so the reveal came early. Vote ids were positional. Bots' last-lash votes were positional. |
| quip-endings, walkins, objects, monologues, dubs, eulogies, lyrics, nonsense | 3 humans each ✔ | 3 phones, 1 round each ✔ | **fixed** | Never ended. Positional vote ids broke voting after any timeout with a missing entry (wrong player scored, or a valid vote rejected). |
| quip-least-funny, wrong-answers (inverted) | ✔ | ✔ | **fixed** | As above, plus zero-vote answers were ignored, so the least-voted answer couldn't win. |
| quip-lies (liar) | 3 humans; 1 human + 3 bots ✔ | ✔ TRUE/LIE toggle, secrets revealed only at scoring | **fixed** | As above. |
| Pack FREAK NIGHT | ✔ | ✔ freaktionary → roast → freaktionary → `pack.done` | **fixed** | Packs existed in code but couldn't be started (no command or button). PLAY AGAIN restarted a single mode instead of the pack. |
| Pack QUICK FIRE | ✔ | ✔ | **fixed** | Same. |
| Poker seat `/play/:ep/seat/:n` (React) | n/a | Existing e2e `sets.spec.ts › poker`: 4 bots + a human play a hand to showdown ✔; vitest `poker.test.ts` 6/6 | **works** (unchanged) | none |
| TNTS vs agents (branch `party-tnts`) | vitest `packages/party` 39/39 ✔ | e2e: camera mode ✔; 2 recorded-feed specs ✘ | **still-broken here (environment)** | Not fixed (branch only). In this sandbox software GL renders 2–7 fps, so 3 s calibration collects fewer than the 20 samples it needs and loops on "No face found". On a phone below ~7 fps the same thing happens. Suggested fix: sample on a timer independent of rAF, or lower `minSamples`. |
| Always-on rooms (branch) | rooms tests ✔ | e2e rooms 3/3 ✔ | works (branch) | none |
| Write-a-minute (branch) | minute tests ✔ | e2e minute 1/1 ✔ | works (branch) | none |
| Alien News (branch) | alien tests ✔ | rendered CLI, not interactive (not rendered here) | works (tests only) | none |

## Edge cases (all games share the plumbing)

| Case | How it was tested | Result |
|---|---|---|
| Player leaves mid-round | Contract (quip collect/vote, freeze vote, drawer leaves, everyone leaves); UI LEAVE button | Room moves on without them. Drawer leaving reveals the word. Under 2 players → `game.done`. ✔ (new `/leave`) |
| Rejoin with token | Contract + UI REJOIN + page reload (token from localStorage) | Same seat, can act next round. Reload inputs are no longer swallowed as dups. ✔ (fixed) |
| Timers expire | Contract with a mocked clock: no input at all, stage-only polling, for all 4 engines; partial input | Every engine reaches a winner. Partial entries vote correctly. ✔ (fixed: stream drives timers; roast loop) |
| Host disconnect | Contract (phones only) + UI (stage tab closed; a token-less stage watches) | Score screens auto-advance after 12 s; the game finishes. ✔ (new) |
| Restart | Contract: save → clear → load | Room, seats and host token survive. ✔ |
| Bad input | Contract fuzz on every POST route (non-JSON, arrays, wrong types, huge text, `<script>` in a code) | No 5xx (was 500 / 415). Code sanitized in `/join`. ✔ (fixed) |
| 2-player minimum | Contract per mode | 1 player → 400 `{need, have}`. 2 players play freaktionary/quip to the end. Roast/freeze need 3 (2 humans + 1 bot OK). ✔ |
| Mid-game join | Contract | Becomes audience (was: seated into a running round). ✔ |
| Bad seat token | UI | Audience screen. ✔ |

## Test suites

- `main` baseline: party scripts 29/36/50/20/12 PASS, `test_funnier_skin` 40, `test_tech_lab` 10. pytest unit 47 + contract 34 (excluding `test_avatar`, which is pre-existing slow/espeak/KeyError).
- Branch: party scripts 29/36/50/20/**16**, skin 40, tech_lab 10. pytest unit+contract **130 passed** (81 + 49 new), 0 new failures.
- New contract tests run against `main`: 47 of 49 fail. That shows the gaps were real, though some failures are only the new contract (e.g. `rounds` in the start reply). See `test-output/new-contract-tests-against-main.txt`.

## Still not done / caveats

- **Edge-tts in this sandbox:** the proxy URL breaks aiohttp, so roast audio shows `failed` and the text reveal carries on. That proves the degrade path. On a normal host it's the free Microsoft voice: no key, no spend. Fish TTS isn't used by any party game.
- **Branch-only games** (TNTS, rooms, minute, Alien News) were not ported. PR #7 is stacked on about 40k lines of unmerged work. The TNTS calibration issue above is noted, not fixed.
- **Ties:** the champion is the first of the tied players. The Ella line says "A tie" when there is one.
- **12 s auto-advance on score screens:** this is a design choice for host-less robustness. Change `SCORED_HOLD` if the host should linger.
- The poker e2e writes screenshots to its default shots/sets dir. They are copied into `shots/poker-seat/`.

## CI (PR #15, head 526a57c, run 40220512261, one loop)
New `party` job ✔ · contracts ✔ · python ✘ with exactly main's 9 `test_avatar.py` failures (134 passed vs 85 on main) · browser ✘ (`test_golden_show`, pre-existing) · formats ✘ (`scripts/freak_format.py` missing, pre-existing). No new failures. Details: `test-output/ci-pr15.md`.
