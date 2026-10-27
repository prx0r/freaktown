# Party games: playtest notes (Oct 2026)

## Status (real-browser verified)
| Game | Status | Proof |
|---|---|---|
| Freaktionary (draw + guess) | Playable on real phones: live drawing on guessers' phones and the stage, rotating drawers, honest tie and no-score results, PLAY AGAIN | `contact/freaktionary_play.jpg`, `PLAYTEST-LIVE.md` |
| Quip Clash (all decks) | Playable: answer, vote (no self-votes), winner screen on stage and phones, PLAY AGAIN, one-click deck picker | `contact/quipclash_play.jpg`, `PLAYTEST-LIVE.md` |
| Roast Relay, Freeze Night, packs | Pass bot and headless UI tests only, **not yet verified by a real-browser playthrough** | `PLAYTEST-BOTS.md`, `contact/*_contact.jpg` |
| Try Not To Smile (branch `party-tnts`) | **Broken at low FPS.** Calibration needs 20 samples in 3 s, so it loops on "No face found" below ~7 fps. Fix not started | see below |

## Lesson learned
Bot/API tests (61/61) and headless UI scripts said every game "worked". A person-like browser agent on a public URL immediately found Freaktionary unplayable: guessers saw no drawing, round 2 skipped, inputs wiped on poll, and a 0–0 game declared a winner. **Every game must pass a real-browser playthrough on a public URL before it's called done.**

## How to play / retest
- `tools/party-playtest/run-live.sh` starts the Flask server on :8090 plus a free cloudflared quick tunnel and prints the URLs.
- Host/TV: `<url>/play`, pick a game, CREATE + HOST. Phones: `<url>/join/<CODE>` or scan the QR code.
- Quick tunnels change URL on every restart. A permanent home (e.g. party.funnier.si) is still to do.

## Harnesses (`tools/party-playtest/`)
- `botplay.py`: HTTP bot phones, 3–4 clients per game, played to a winner.
- `uiplay.py`, `uiedge.py`: headless Chromium UI flows and edge cases.
- `pwplay.py`: Playwright over a public URL with real mouse and touch strokes (set `CHROME_PATH` if Playwright's browser is unavailable).
- `contact.py`, `sheet.py`: contact-sheet builders.

## Open weak spots
- Strokes sync by polling, so guessers see them 0.5–1 s late.
- Quip Clash scores only the top answer per prompt; a runner-up with votes gets 0 (the rule is shown on screen).
- After BACK TO LOBBY, players must press I'M READY again.
- The optional "freak" field on the join page confuses testers.
- TNTS calibration fix to do: time-window sampling with a minimum number of good samples, throttled detection, a retry with clear UI, a "skip, use default baseline" button, and a no-face timeout that can't stall a round.
- Pre-existing red CI on main (`test_avatar.py` KeyError 'slug', `test_golden_show` 500, missing `scripts/freak_format.py`) is unrelated.
