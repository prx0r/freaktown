#!/usr/bin/env python3
"""Freak.town SDK — the interoperability layer, nothing else.

Five contracts: Character, Participant, Controller, Format, Event.
The game never knows whether a contestant is human, agent, copilot, or
a dumb script. It only sees a Participant. That is the whole trick.

We do NOT build: agent frameworks (use yours), realtime engines (use
LiveKit/Colyseus/DO via adapters), avatar formats (GLB/VRM + manifest).
A Freak is the portable character record; everything else is a renderer,
a transport, or a brain you already have.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Protocol


# ── Character: the persistent object. Games are temporary environments. ──

@dataclass
class Character:
    id: str
    name: str
    bio: str = ""
    appearance: dict = field(default_factory=dict)  # {asset, format} GLB/VRM
    voice: dict = field(default_factory=dict)
    personality: dict = field(default_factory=dict)
    memories: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)
    relationships: dict = field(default_factory=dict)
    control_mode: str = "AUTONOMOUS"  # HUMAN | COPILOT | AUTONOMOUS

    @staticmethod
    def from_bundle(slug: str, character: dict, avatar: dict | None = None) -> "Character":
        """Freak Town bundle files → portable Character. Renderers vary;
        the record is stable."""
        rt = ((avatar or {}).get("appearance") or {}).get("runtime", {})
        return Character(
            id=slug,
            name=character.get("name", slug),
            bio=character.get("premise", ""),
            appearance={"asset": rt.get("uri", ""),
                        "format": rt.get("format", "glb")},
            voice={"voice_id": character.get("voice", "")},
            personality={"vibe": character.get("vibe", "")},
        )

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps({
            "id": self.id, "name": self.name, "bio": self.bio,
            "appearance": self.appearance, "voice": self.voice,
        }, sort_keys=True).encode()).hexdigest()[:16]


# ── Events: what every controller observes ──

@dataclass
class FreakEvent:
    type: str                      # e.g. performance.request, round.results
    payload: dict = field(default_factory=dict)
    seq: int = 0


@dataclass
class Action:
    kind: str                      # submit | vote | choose | move | pass
    payload: dict = field(default_factory=dict)


@dataclass
class FormatContext:
    format_id: str
    round_id: str
    participant_ids: list
    state: dict = field(default_factory=dict)


# ── Controller: how ANY mind enters entertainment ──
# A human phone, a Claude agent, an OpenClaw bot, or a script all
# implement these two methods. Nothing else is required. Ever.

class FreakController(Protocol):
    def observe(self, event: FreakEvent) -> None: ...
    async def act(self, available: list[Action],
                  context: FormatContext) -> Action: ...


# ── Built-in controllers (all interchangeable) ──

class ScriptedController:
    """Deterministic stand-in: replays a script. Tests, NPCs, demos."""

    def __init__(self, script: dict | None = None):
        self.script = script or {}
        self.seen: list[str] = []

    def observe(self, event: FreakEvent) -> None:
        self.seen.append(event.type)

    async def act(self, available: list[Action],
                  context: FormatContext) -> Action:
        key = f"{context.round_id}:{available[0].kind}" if available else "pass"
        if key in self.script:
            want = self.script[key]
            for a in available:
                if a.payload.get("text") == want or a.kind == want:
                    return a
        return available[0] if available else Action("pass", {})


class HumanController(ScriptedController):
    """A human on a phone. Same interface; acts arrive via UI instead of
    a script. Queued inputs replay in order (tests drive it directly)."""

    def __init__(self):
        super().__init__({})
        self.queue: list[Action] = []

    def push(self, action: Action):
        self.queue.append(action)

    async def act(self, available: list[Action],
                  context: FormatContext) -> Action:
        if self.queue:
            return self.queue.pop(0)
        return Action("pass", {})


class AgentController:
    """Your agent, whatever framework it uses. Wrap its think-callable:
    fn(prompt) -> {"kind": ..., "payload": {...}}. Freak.town never sees
    the framework — only the Action that comes back."""

    def __init__(self, think, label: str = "agent"):
        self.think = think
        self.label = label
        self.seen: list[str] = []

    def observe(self, event: FreakEvent) -> None:
        self.seen.append(event.type)

    async def act(self, available: list[Action],
                  context: FormatContext) -> Action:
        prompt = (f"You are {self.label} in {context.format_id} "
                  f"round {context.round_id}. Options: "
                  + ", ".join(f"{a.kind}:{a.payload}" for a in available))
        try:
            out = self.think(prompt) or {}
        except Exception:
            out = {}
        for a in available:
            if a.kind == out.get("kind"):
                merged = dict(a.payload)
                merged.update(out.get("payload", {}))
                return Action(a.kind, merged)
        return available[0] if available else Action("pass", {})


class CopilotController:
    """HUMAN + AI: the agent drafts, the human approves (or times out and
    the draft goes through). One seat, two minds."""

    def __init__(self, agent: AgentController, human: HumanController,
                 timeout_approves: bool = True):
        self.agent = agent
        self.human = human
        self.timeout_approves = timeout_approves

    def observe(self, event: FreakEvent) -> None:
        self.agent.observe(event)
        self.human.observe(event)

    async def act(self, available: list[Action],
                  context: FormatContext) -> Action:
        draft = await self.agent.act(available, context)
        if self.human.queue:
            approval = self.human.queue.pop(0)
            if approval.kind == "pass":
                return draft if self.timeout_approves else Action("pass", {})
            return approval
        return draft if self.timeout_approves else Action("pass", {})


# ── Participant: character × controller. The game sees ONLY this. ──

@dataclass
class Participant:
    character: Character
    controller: Any  # any FreakController

    @property
    def id(self) -> str:
        return f"contestant:{self.character.id}"

    async def perform(self, action: Action,
                      context: FormatContext) -> dict:
        """Run one turn: act, receipt fragment. All controllers expose
        async act(), so every seat awaits identically."""
        acted = await self.controller.act([action], context)
        return {"participant": self.id, "character": self.character.name,
                "action": {"kind": acted.kind, "payload": acted.payload}}


# ── Format binding: contestants into the existing format runtime ──

def run_match(manifest: dict, participants: list[Participant],
              submissions: dict, event_id: str = "") -> dict:
    """Score submissions through the declarative format runtime.
    The runtime never learns controller kinds — only ids and scores."""
    import format_runtime as FR
    run = FR.FormatRun(manifest, event_id=event_id or f"evt_sdk_{manifest['id']}")
    pids = [p.id for p in participants]
    sub = {rid: {pid: scores.get(pid) for pid in pids if pid in scores}
           for rid, scores in submissions.items()}
    receipt = run.run(pids, sub)
    return {"receipt": receipt, "events": run.events}
