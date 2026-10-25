# Party modes (party.py): how a game runs end to end

Stage `/party/<code>/stage`, phones `/party/<code>/play`, one Flask server.
Every mode in `MODES` can be started from the stage (one button per mode, plus
the packs) and plays to a crowned winner.

## Lifecycle

1. `POST /party/create` → `{code, host_token}` (the `/play` page does this and
   stores the token; `?host=<token>` on the stage also works).
2. Phones `POST /party/<code>/join {name, freak}` → `seat_token`. Joining
   mid-game or after `lock` gives an audience seat.
3. Host `POST /party/<code>/host {host_token, cmd: "start", mode | pack,
   rounds?, target?, deck?}`. Minimum players are enforced (`need`/`have` in
   the 400). Starting again is "play again" and resets scores.
4. Rounds run on their own: every active player acting moves the phase on;
   otherwise the deadline does (90 s collect, 60 s vote, 120 s draw). Score and
   reveal screens hold `SCORED_HOLD` (12 s), then advance, so the game keeps
   going if the host tab closes. Deadlines are lazy: any `/view`, `/input`,
   `/host` or `/stream` request after the deadline applies them.
5. Standalone games end after `rounds` (freaktionary: one turn per player;
   roast-relay and quip-*: 3) with `game.done`; freeze-night ends after its
   playlist with `night.done`; packs end with `pack.done`.
6. `cmd: "lobby"` returns everyone to the lobby (scores cleared, room open).

## Real phones (what the browser pages guarantee)

- **Drawing**: the drawer's canvas uses pointer events with pointer capture
  (mouse, pen, touch; a touch/mouse fallback for old browsers),
  `touch-action:none`, a segment between every sampled point, and ordered
  ~150 ms batches tagged with a `stroke` id. The server joins batches of one
  stroke into one line (`draw.batch {stroke, points}`, `draw.clear`).
- **Watching**: guessers' phones and the stage draw the strokes on a read-only
  canvas from `freaktionary.strokes`, redrawn only when `freaktionary.rev`
  changes. The drawing stays up on the reveal.
- **Inputs never reset**: a phone rebuilds its screen only when the screen's
  structure changes (new screen, round or options); text updates in place, so
  focus and typed text survive every poll. Drafts are kept in localStorage per
  seat and screen, so a reload or a phone that drops the tab keeps them.
- **Host buttons**: NEXT ROUND (FINAL SCORES on the last round) shows only
  between rounds; a separate SKIP shows mid-round after 8 s. The stage sends
  `expect` (the `phase_key` it is looking at) with `advance`; the server
  ignores a stale one, any advance on a screen younger than 2.5 s, and a
  mid-round skip younger than 7.5 s, so a late or double click can never skip
  a round nobody has played. A host skip of a prompt nobody answered re-rolls
  it without using up a round. Words and prompts do not repeat within a game.
- **Honest results**: `result {kind: win|tie|none, names, headline, scores}`.
  Only a single leader is crowned (`champion`, `winner`); a shared top score is
  "IT'S A TIE", and a game where nobody scored says "NOBODY SCORED". Stage
  and phones both show the final scoreboard; PLAY AGAIN keeps the mode and
  round count.
- **Scoring is shown** on every phone and the stage: Freaktionary "+2 for the
  guess, +1 to the drawer"; Quip Clash normal decks "most votes wins up to
  +100 by vote share, +25 sweep"; the round results list each answer with its
  author, votes and points.

## Leaving and coming back

- `POST /party/<code>/leave {seat_token}`: in the lobby the seat is freed;
  mid-game the seat stays (so vote ids never shift) but nobody waits on it.
  If fewer than 2 players remain the game ends.
- `POST /party/<code>/join {seat_token}` with the same token rejoins.
- Phones send string `client_seq` values (`<ms>-<n>`), so a reloaded page is
  never mistaken for a duplicate retry.

## Bots

`cmd: "bots", n` seats deck-driven contestants ($0, no API) in every mode:
freaktionary bots draw and guess, roast-relay bots roast and vote, freeze-night
and quip bots write and vote.

## Voice

Roast Relay tries a free edge-tts read of the assembled set after the text
reveal (`generation.ready`). It is best-effort; `PARTY_TTS=0` turns it off
(tests and CI do). No party mode calls an LLM.

## Tests

```bash
PARTY_TTS=0 python -m pytest tests/contract/test_party_games.py -q   # every game + edge cases
python test_party.py && python test_quip_clash.py && python test_freeze_night.py \
  && python test_solo_night.py && python test_allbots.py
```

The `party` CI job runs both.
