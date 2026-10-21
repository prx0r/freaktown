#!/usr/bin/env python3
"""Party Pi agents: freaktown bots as agents with pi harness backends.

ADDITIVE ONLY: new file, no rewrites. Deck bots in party.py stay the
default ($0, deterministic, CI-safe). When explicitly enabled, bot seats
act through qpbot's Pi harness backend (multi-turn agent, session per
seat, vault-held keys) and fail CLOSED back to decks on any error,
timeout, or missing key/binary.

Enable: PARTY_PI_AGENTS=1 (default off — tests never touch network).
Keys: vault-held only (never in tree). Spend: ask-first; off means $0.

Backend order per call:
  1. qpbot agentcom.pi_agent.chat (Pi CLI harness, sessions) — if importable
  2. None -> caller uses deck fallback (never invents, never blocks room)

Models: qwen backend is QWEN_MODEL (default qwen3.8-omni-flash) on the owner's
Aliyun Model Studio key (probed 200 live); pi backend runs deepseek-v4-flash
on the OpenCode Go key. Jev-1.14 eyes stay on the OpenRouter key (Jev-ONLY
per owner rule). Fish voice stays s2.1-pro-free ($0).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent


def _load_env():
    # Same rule as scripts/interpret_joke.py: the repo .env is the owner's
    # explicit config and OVERRIDES inherited shell env (this box's
    # persistent shell may export platform keys with the same names).
    env = _BASE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()


_load_env()

PI_MODEL = os.getenv("PARTY_PI_MODEL", "deepseek-v4-flash")

# Qwen Omni (Model Studio Singapore, OpenAI-compatible). Key lives in
# freaktown/.env (QWEN_API_KEY, 600, gitignored) — never in tree, never logged.
_QWEN_DEFAULT_BASE = "https://ws-h6o7g3oq9mc7u24u.ap-southeast-1.maas.aliyuncs.com"
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen-flash-character")
# Backend order: auto (qwen first when its key is present, else pi),
# qwen, or pi. Default-on Qwen because it is a single HTTPS call with the
# repo key; pi needs the qpbot checkout + vault keys + sessions.
BACKEND = os.getenv("PARTY_PI_BACKEND", "auto")

QPBOT_ROOT = "/root/qpbot"
PI_CANDIDATES = [
    "/root/qpbot/pi/packages/coding-agent/dist/cli.js",
    "/root/qpbot/connectors/pi-xmrecon/node_modules/@earendil-works/pi-coding-agent/dist/cli.js",
]

SYSTEM_BY_MODE = {
    "roast-relay": ("You are a party-game contestant. Write ONE roast line "
                    "(<=30 words) about the target. Funny, no slurs. Reply with ONLY the line."),
    "freaktionary": ("You are guessing a drawing. Reply with ONLY your guess "
                     "(<=60 chars, lowercase)."),
    "freeze-night": ("You are an improv contestant. Reply with ONLY your entry "
                     "(one line, <=180 chars)."),
    "quip": ("You are a comedy contestant. Reply with ONLY your entry "
             "(one line, <=180 chars)."),
    "stone-face": ("Confess something TRUE+funny about yourself in one line "
                   "(<=120 chars). Reply with ONLY the confession."),
    "poker": ("You hold cards. Reply with ONLY one word: check, call, bet, or fold."),
    "interview-judge": ("You are judging a comedy set. Reply in character, one question or verdict line."),
    "interview-performer": ("You are the act, answering your judge. Stay in character, one or two lines."),
}

# Persona: who the bot IS, on top of what the game asks it to do. This is the
# "character model" technique, and it ports across models: qwen-flash-character
# and qwen-plus-character take the whole persona in the system message; omni
# models take the same system text AND add audio/image/video input plus the
# realtime socket. So the persona lives here, the model is picked per call
# site via QWEN_MODEL (text seats: qwen-flash-character, cheap + role-stable;
# ears/eyes/live voice: qwen3.8-omni-flash or the realtime model).
# PARTY_PI_PERSONA fixes one voice for every seat; unset = each seat gets its
# own name-based voice so nights stay legible ("Bruno said X").
PERSONA = os.getenv("PARTY_PI_PERSONA", "").strip()


def _persona(seat: str) -> str:
    if PERSONA:
        return PERSONA
    name = (seat.split("-")[0] or "ralph").title()
    return (f"You are {name}, a quick-witted party regular with a sharp "
            f"tongue and a short memory for grudges. Stay in character in "
            f"every reply.")


def enabled() -> bool:
    return os.getenv("PARTY_PI_AGENTS", "0") == "1"


def pi_cli_present() -> str | None:
    import pathlib
    for p in PI_CANDIDATES:
        if pathlib.Path(p).exists():
            return p
    return None


def _qwen_line(mode: str, prompt: str, seat: str,
               _system_override: str | None = None) -> str | None:
    """One Qwen turn (character model or omni — same system-prompt technique).
    Fail-closed: any miss returns None (deck takes it).

    party.py bot calls are short lines, so max_tokens stays small (~$0.0001
    a turn at flash rates). The key never leaves this function: in the POST
    header only, never logged.
    """
    import json
    import urllib.request
    key = os.environ.get("QWEN_API_KEY", "")
    if not key:
        return None
    base = os.environ.get("QWEN_BASE_URL", _QWEN_DEFAULT_BASE).rstrip("/")
    model = os.environ.get("QWEN_MODEL", QWEN_MODEL)
    system = (_system_override
              or _persona(seat) + "\n" + SYSTEM_BY_MODE.get(mode, SYSTEM_BY_MODE["quip"]))
    body = json.dumps({
        "model": model,
        "max_tokens": 120,
        "temperature": 0.9,
        # omni-flash thinks by default and eats the whole budget on short
        # party lines (376 reasoning tokens on a 60-token cap). Off.
        "enable_thinking": False,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": prompt[:1500]}],
    }).encode()
    try:
        req = urllib.request.Request(
            base + "/compatible-mode/v1/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + key,
                     "User-Agent": "freaktown-party/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        content = ((d.get("choices") or [{}])[0].get("message", {})
                   or {}).get("content") or ""
        # The omni model may wrap work in reasoning_content; the answer text
        # is what lands in content. Clean to one line the game can print.
        line = content.strip().splitlines()
        line = (line[0].strip().strip("\"'") if line else "")[:180]
        return line or None
    except Exception:
        return None


def _pi_line(mode: str, prompt: str, seat: str,
             _system_override: str | None = None) -> str | None:
    """Original pi-harness path (qpbot checkout + sessions + vault keys)."""
    if not enabled():
        return None
    try:
        sys.path.insert(0, QPBOT_ROOT)
        from agentcom.pi_agent import chat as pi_chat  # noqa
    except Exception:
        return None
    if pi_cli_present() is None:
        # pi_agent would fail on missing binary; fail closed early.
        return None
    system = (_system_override
              or _persona(seat) + "\n" + SYSTEM_BY_MODE.get(mode, SYSTEM_BY_MODE["quip"]))
    try:
        import concurrent.futures as _f
        with _f.ThreadPoolExecutor(max_workers=1) as ex:
            fut = ex.submit(pi_chat, prompt[:1500], f"party-{seat}",
                            system, PI_MODEL)
            r = fut.result(timeout=45)
        reply = (r or {}).get("reply", "").strip().splitlines()
        line = (reply[0].strip() if reply else "")[:180]
        if not line or line.startswith("No API key"):
            return None
        return line
    except Exception:
        return None


def agent_line(mode: str, prompt: str, seat: str, timeout_note: str = "",
               system: str | None = None) -> str | None:
    """One agent bot turn. Fail-closed: disabled flag, missing keys/binary,
    timeouts, empty replies all return None (caller uses the $0 deck).
    Never raises into game code.

    BACKEND order (PARTY_PI_BACKEND): auto (default) = qwen when its repo
    key is present, else pi; qwen = qwen only; pi = pi harness only.
    Pass system= to override the mode's default system prompt (the show
    interview does this for Killella + the performer).
    """
    if not enabled():
        return None
    base_system = system if system else SYSTEM_BY_MODE.get(mode, SYSTEM_BY_MODE["quip"])
    order = ["qwen", "pi"] if BACKEND == "auto" else [BACKEND]
    for which in order:
        if which == "qwen":
            line = _qwen_line(mode, prompt, seat, _system_override=base_system)
        elif which == "pi":
            line = _pi_line(mode, prompt, seat, _system_override=base_system)
        else:
            line = None
        if line:
            return line
    return None


def roast_line(target: str, seat: str) -> str | None:
    return agent_line("roast-relay", f"Target: {target}. Roast them in one line.", seat)


def quip_entry(prompt_text: str, seat: str) -> str | None:
    return agent_line("quip", f"Prompt: {prompt_text}", seat)


def vote_choice(options: list[str], seat: str) -> str | None:
    """Choice via Pi agent; options are index strings. None = deck vote."""
    if not options:
        return None
    r = agent_line("quip", f"Pick the funniest index from {options}. Reply with ONLY the index.", seat)
    return r if r in options else None
