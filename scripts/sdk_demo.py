#!/usr/bin/env python3
"""Same format, four different minds. The game can't tell them apart.

  python3 scripts/sdk_demo.py
Tom (human) vs Claude (agent) vs OpenClaw (agent) vs NPC (scripted)
 walk into the SAME open-mic. Receipt proves it.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from format_runtime import load_format
from sdk import (Action, AgentController, Character, CopilotController,
                 FormatContext, HumanController, Participant, ScriptedController,
                 run_match)


def claude_think(prompt: str) -> dict:
    return {"kind": "submit", "payload": {"score": 8.5}}


def openclaw_think(prompt: str) -> dict:
    return {"kind": "submit", "payload": {"score": 7.5}}


async def main():
    manifest = load_format("formats/comedy.open-mic")
    tom = Participant(Character("tom", "Tom's Freak", control_mode="HUMAN"),
                      HumanController())
    tom.controller.push(Action("submit", {"score": 9.5}))
    claude = Participant(Character("claude", "Claude Freak", control_mode="AUTONOMOUS"),
                         AgentController(claude_think, label="Claude Freak"))
    claw = Participant(Character("claw", "OpenClaw Freak", control_mode="AUTONOMOUS"),
                       AgentController(openclaw_think, label="OpenClaw Freak"))
    npc = Participant(Character("npc", "NPC Freak", control_mode="AUTONOMOUS"),
                      ScriptedController())
    seats = [tom, claude, claw, npc]

    # every seat performs one identical turn through one interface
    ctx = FormatContext("comedy.open-mic", "open", [p.id for p in seats])
    for p in seats:
        out = await p.perform(Action("submit", {"score": 7.0}), ctx)
        print(f"{out['character']:15s} -> {out['action']}")

    # ...then the format runs them all as pure contestants.
    # open top-2 of [6,7,8,9] = claw + npc; final decides between them.
    scores = {"open": {p.id: 6.0 + i for i, p in enumerate(seats)},
              "final": {seats[2].id: 8.0, seats[3].id: 8.7}}
    out = run_match(manifest, seats, scores, event_id="evt_sdk_demo")
    print("winner:", out["receipt"]["results"]["winner"])
    print("root:", out["receipt"]["event_log_root"][:12])


if __name__ == "__main__":
    asyncio.run(main())
