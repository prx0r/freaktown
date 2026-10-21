"""Proactive table talk. Run: python3 test_chatter.py (no network, $0)."""
import os
import time

# Dry by design: .env is never loaded in tests; flags are explicit here.
os.environ["PARTY_CHATTER"] = "1"
os.environ["PARTY_PI_AGENTS"] = "0"

import party_chatter as ch
from app import app

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL", name)


def room(mode="poker", bots=3, phase="playing", seen=True):
    r = {"code": "TST1", "phase": phase, "mode": mode,
         "players": {f"b{i}": {"name": f"Bot{i}", "bot": True, "score": 0}
                     for i in range(bots)},
         "mode_state": {"phase": "betting", "pot": 12, "hand": 2,
                        "board": ["2h", "9c"]},
         "events": [{"kind": "player.bet"}], "seq": 7}
    if seen:
        r["_seen_at"] = time.time()  # a viewer is polling this table
    return r


# 1. flag off silences everything
os.environ["PARTY_CHATTER"] = "0"
check("flag off -> no line", ch.tick(room()) is None)
os.environ["PARTY_CHATTER"] = "1"

# 2. eligible room talks (dry deck, no network with PI_AGENTS=0)
r = room()
msg = ch.tick(r)
check("playing+bots -> line", isinstance(msg, dict) and bool(msg.get("text")))
check("line has speaker", bool(msg and msg.get("by")))
check("dry mode (no live)", msg and msg.get("live") is False)

# 3. throttle: immediate second tick silent
check("throttled within gap", ch.tick(r) is None)

# 4. no bots / not playing / no viewer -> silent
check("no bots -> silent", ch.tick(room(bots=0)) is None)
check("lobby -> silent", ch.tick(room(phase="lobby")) is None)
check("ghost (nobody watching) -> silent", ch.tick(room(seen=False)) is None)

# 5. determinism: same room state, same deck line (seeded by seq+seen)
a = ch.tick({**room(), "_chatter_at": 0.0, "seq": 7})
b = ch.tick({**room(), "_chatter_at": 0.0, "seq": 7})
check("seeded deck deterministic", a["text"] == b["text"])

# 6. poker context never leaks secrets (prompt has no hole cards)
ctx = ch._state_context(room())
check("context is public-only", "hole" not in ctx and "pot=" in ctx)

# 7. deck vocabulary
check("poker deck exists", len(ch.DECKS["poker"]) >= 6)

# 8. stage renders chat events (source check, no browser)
import party
stage = party.STAGE_TEMPLATE
check("stage handles ev.kind chat", "ev.kind === 'chat'" in stage)
check("stage chat shows speaker", "ev.by" in stage.split("ev.kind === 'chat'")[1][:200])

# 9. dry line length sane
check("line <= 120 chars", len(msg["text"]) <= 120)

print(f"\n{passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
