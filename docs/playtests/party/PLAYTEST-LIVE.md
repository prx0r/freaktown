# Live real-browser playtest: FREAKTIONARY + QUIP CLASH (2026-10-26 ICT)

**Live tunnel:** https://directive-potentially-strand-london.trycloudflare.com
- Host (TV / laptop): `/play` → pick a card → **CREATE + HOST** (opens `/party/<CODE>/stage`)
- Phones: `/join/<CODE>` (or scan the QR on the stage)

The earlier tunnel (`tourism-promise-pool-providers…`) died when the sandbox restarted mid-session; this one replaced it.
Server: `PARTY_TTS=0 PORT=8090 python3 app.py` in the repo root, logging to `/tmp/ft.log`. Tunnel log: `/tmp/cf.log`.
To restart after a reboot:
- server + tunnel: `tools/party-playtest/run-live.sh`

**Code:** PR #15 https://github.com/prx0r/freaktown/pull/15 is one squashed commit on main `c3d2f4e`:
- remote head `68d50f343f268920be9bcb73fa40a6918b60129d`
- local `ac54fdf`
- trees match

Not merged.

## How it was verified (no bots, no API-only checks)

1. **Person-like browser agent** played through the public tunnel: 4 rounds of passes per game (8 sessions), with exact on-screen text captured. Raw agent notes were kept outside the repo.
2. **Headless Chromium (Playwright)** over the **public tunnel** with real input: `page.mouse.move(..., steps=8)` drags, and CDP `Input.dispatchTouchEvent` finger strokes for round 2. It checks the ink pixels on the drawer's canvas, the **guesser's phone** canvas and the **stage** canvas. It also checks:
   - typed text and focus surviving polls
   - drafts surviving a page reload
   - a fast double-click on ADVANCE
   - the winner screens
   - that PLAY AGAIN is stable across polls (same DOM node) and restarts with 0 scores and the same round count

   Script: `pwplay.py`. Logs: `freaktionary_pw.log`, `quip_pw.log`. Last runs: **0 failures** for both games (rooms 3UHNMU, QANK43).
3. **Contact sheets:**
   - `freaktionary_play.jpg`: the drawing is visible on the guesser's phone and the stage in both rounds (mouse in round 1, touch in round 2), plus the reveal, winner and PLAY AGAIN screens.
   - `quipclash_play.jpg`: prompt with the scoring rule, voting, round results on the stage and a phone, winner screens, PLAY AGAIN.
   - Emoji show as boxes only because headless Chromium has no emoji font. Real phones render 🏆🥇.

## Numbered issues

| # | Issue | Status | Evidence |
|---|---|---|---|
| 1 | Guessers saw no drawing | **Fixed**: read-only canvas on the guess and reveal screens, redrawn when `rev` changes | All agent passes saw the drawing on the guesser phone; Playwright guesser ink ~7100 px in both rounds |
| 2 | Strokes not on the stage | **Fixed**: stage paints `freaktionary.strokes` | Agent passes 2–4 saw red strokes on the stage; Playwright stage ink ~7100 px |
| 3 | Dots, not lines | **Fixed**: pointer events + `setPointerCapture`, `touch-action:none`, touch/mouse fallback, coalesced events, a segment between every point, ordered ~150 ms batches with a `stroke` id that the server joins | Server stored 2 continuous strokes (161 + 33 pts) for a mouse drag and for a touch drag. Agent passes 1–3 drew continuous lines; pass 4's tool sent only a single pointerdown (one point per "drag"; server log shows 1-point batches), which is a limit of that tool's synthetic drag |
| 4 | Typed guess wiped by re-render | **Fixed**: a screen is rebuilt only when its structure changes, text updates in place, and drafts persist per seat in localStorage | "hmm a" + focus survived 2.5 s of polls; drafts survived a reload (Playwright + agent pass 2) |
| 5 | Round 2 skipped to its reveal | **Fixed** after 3 iterations. Causes found: double click; the reveal timer advancing under the host's finger; one button meaning NEXT ROUND or SKIP depending on the moment. Now there are **separate** NEXT ROUND (between rounds only) and dashed SKIP (mid-round, after 8 s) buttons, and `advance` carries `expect=<phase_key>`. The server ignores stale clicks, any advance within 2.5 s of a new screen, and a mid-round skip within 7.5 s | Agent pass 4 clicked NEXT ROUND late in both games: round 2 was a real drawing / collecting phase with a new drawer / new prompt. Contract tests cover it |
| 6 | 0–0 showed "WINNER: Ana" | **Fixed**: `result.kind` win / tie / none. "NOBODY SCORED", "IT'S A TIE: A & B" (ties share a medal), "X WINS!" | Agent: 0–0 → "NOBODY SCORED"; Quip tie → "🤝 IT'S A TIE: Ana & Ben" |
| 7 | START visible mid-game | **Fixed**: the picker and START show only in the lobby | Agent + Playwright |
| 8 | Game-over buttons re-render / missed clicks | **Fixed**: DOM is written only on change; stable footer | Playwright: same node after polls; agents: one click each. One agent's element list missed the buttons once (clicked by coordinate) after the CSS `display:none` fix; the pulse animation was removed afterwards |
| 9 | No Quip winner screen | **Fixed**: stage and every phone show the headline + final scoreboard + "You scored N" | Agent pass 4 exact text: "FINAL SCORES / GAME OVER / IT'S A TIE: Ana & Ben / 🥇 Ana: 67 / … / You scored 67." |
| 10 | No PLAY AGAIN | **Fixed**: PLAY AGAIN keeps the mode and round count; BACK TO LOBBY | Agent: scores 0, still 2 rounds |
| 11 | Scoring unexplained | **Fixed**: the rule line is on phones and the stage, and round results show author, votes and points per answer | "Most votes wins the round: up to +100 (your share of the votes), +25 bonus if everyone picks you" |
| 12 | Deck picker first click | **Fixed**: picker buttons select (highlight + "START <deck>"); START starts | Agent pass 4: one click → "START FUNNIER ENDING" |
| + | Quip phone inputs reset on poll | **Fixed** (same renderer as #4) | Playwright: 3 phones' text survived polls + reload |

## Extra problems the real-browser runs found, now fixed
- Quip: SKIP TO VOTING on a prompt nobody had answered **ended the game** (it counted as a round). A host skip now re-rolls the prompt in the same round.
- Prompts and words repeated across rounds. They don't repeat within a game now.
- Voters thought their answer was lost. The ballot now says "(Your own answer isn't on your ballot.)"
- A hung request over the tunnel could stop a phone's poll loop. Requests now time out after 6 s.
- The 50 ms draw rate-limit silently dropped the last batch of a stroke. It is replaced by a 30 batches/s flood guard.
- The draw timer went from 90 s to 120 s, since slower players ran out of time.

## Tests
- `tests/contract/test_party_games.py`: 62 pass. New tests cover:
  - every Freaktionary round is a live drawing turn with drawer rotation
  - stale, double and late ADVANCE never skips a round
  - no-score and tie results
  - stroke join and sync to the guesser and stage, plus clear
  - drawing kept on the reveal and rules shown
  - no repeated words or prompts
  - Quip results explain the score
  - skipping an empty prompt keeps the round
  - PLAY AGAIN keeps rounds
  - stage and phone page contracts
- `test_party.py` 29/29, `test_quip_clash.py` 36/36, `test_freeze_night.py` 50/50, `test_solo_night.py` 20/20, `test_allbots.py` 16/16 (Freaktionary bot nights may now honestly end in a tie).

## CI (PR #15)
- `party` job (all party games) and `contracts`: **green** on `58ff6ec` (loop 1) and on the final head `68d50f3` (loop 2, run 40229368491).
- `python`, `browser` and `formats` fail on **main `c3d2f4e` too**, so they predate this PR. The failures are avatar contract tests (`KeyError: 'slug'`), 3 unit tests in `tests/unit/test_freaktown.py`, the golden-show e2e (HTTP 500), and freak_format. Nothing in this PR touches them.

## Remaining weak spots
- Drawing only syncs by polling (phones 500 ms, stage 450 ms), so guessers see strokes ~0.5–1 s late. That's fine for a party, but it isn't WebSocket-smooth.
- The quick Cloudflare tunnel is ephemeral. If the sandbox restarts, the URL changes (it happened once this session).
- Quip normal scoring is winner-takes-share: a 1-vote runner-up gets 0. The rule is now stated on screen, but players may still expect points per vote.
- Players must press I'M READY again after BACK TO LOBBY. The join page asks for an optional "freak" name, which one tester found confusing.
- The browser agent drives one tab at a time, so its runs are slower than real people. Its timer-expiry "nobody got it" rounds were agent latency, not bugs.
