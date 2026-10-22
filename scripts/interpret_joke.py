#!/usr/bin/env python3
"""Joke semantic interpreter on OpenCode Go + mimo-v2.5 ONLY.

Port of characters' audition/semantic_interpreter.py (which uses OpenRouter
+ Qwen): same SYSTEM_PROMPT, same MECHANISMS, same joke_event.json shape —
different wire (Go endpoint, session header, own UA). No OpenRouter, no Qwen.

Key/model come from funnier/.env (OPENCODE_GO_API_KEY, OPENCODE_GO_MODEL).
Each call is a few hundred tokens on the owner's Go subscription.

Usage:
  /usr/bin/python3 scripts/interpret_joke.py --test
  /usr/bin/python3 scripts/interpret_joke.py "transcript..." [--character character.json] [--earlier "earlier beats"]
"""
import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def load_env():
    # The repo .env is the owner's explicit config: it OVERRIDES inherited
    # shell env (this box's persistent shell may export platform keys with
    # the same names — wrong account, subscription errors).
    env = BASE / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()


load_env()
GO_URL = os.environ.get("OPENCODE_GO_BASE_URL",
                        "https://opencode.ai/inference/go/openai/v1") + "/chat/completions"
GO_KEY = os.environ.get("OPENCODE_GO_API_KEY", "")
GO_MODEL = os.environ.get("OPENCODE_GO_MODEL", "mimo-v2.5")

MECHANISMS = {
    "setup_punchline", "misdirection", "escalation", "callback",
    "self_deprecation", "deadpan", "anti_humor", "sarcasm",
    "absurdism", "blue_humor", "status_reversal",
    "identity_contradiction", "incongruity", "benign_violation",
    "garden_path", "double_interpret", "split_knowledge",
    "expose_self_blindness", "displacement", "not_a_joke",
}

SYSTEM_PROMPT = """You are a comedy semantic interpreter. Your ONLY job is to \
understand what a joke MEANS — not to predict whether anyone laughs.

You receive:
1. The transcript of what was said
2. Character graph context (who is speaking, their identity, contradictions)
3. Earlier context (earlier setup, callbacks)

You output a JSON object describing the joke's structure:
- mechanism: which comedic mechanisms are at work
- setup: what the comedian establishes
- expected: what the audience expects
- reveal: what actually happens
- character_conflict: how this conflicts with character identity
- irony_detected: is there irony?
- literal_meaning vs intended_meaning: for sarcastic/ironic jokes
- confidence_in_interpretation: how sure are you (0.0-1.0)

CRITICAL RULES:
1. If the segment is NOT a joke (ordinary statement, question, etc.), \
set mechanism to ["not_a_joke"] and confidence to 0.9+.
2. If you are UNSURE about the interpretation, set confidence < 0.7 \
and explain in uncertainty_reason. DO NOT fabricate an explanation.
3. Ground character contradictions in the provided character graph. \
Do not invent character traits.
4. Distinguish literal from intended meaning for sarcasm/irony.
5. For callbacks, identify WHAT is being called back to.

Valid mechanisms: setup_punchline, misdirection, escalation, callback, \
self_deprecation, deadpan, anti_humor, sarcasm, absurdism, blue_humor, \
status_reversal, identity_contradiction, incongruity, benign_violation, \
garden_path, double_interpret, split_knowledge, expose_self_blindness, \
displacement, not_a_joke.

Reply with ONLY the JSON object, no other text."""


def interpret_joke(transcript, character_graph=None, earlier_context="",
                   beat_id="", session="funnier-interpret"):
    if not GO_KEY:
        raise RuntimeError("OPENCODE_GO_API_KEY not found")
    if isinstance(character_graph, dict):
        char_ctx = json.dumps(character_graph, indent=2)
    elif isinstance(character_graph, str):
        char_ctx = character_graph
    else:
        char_ctx = "(no character context provided)"
    import subprocess as _sp
    # NOTE: Go fingerprint-filters Python-urllib (identical headers via curl
    # work fine), so transport is curl. No OpenRouter anywhere on this path.
    body = json.dumps({
        "model": GO_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"Transcript:\n{transcript}\n\nCharacter context:\n{char_ctx}\n\n"
                f"Earlier context (earlier beats, callbacks):\n{earlier_context or '(none)'}\n\n"
                "Interpret this joke. Output JSON matching the schema.")},
        ],
        # NOTE: no temperature — the Go route errors on it for mimo-v2.5.
        "max_tokens": 1200,
    })
    try:
        proc = _sp.run(
            ["curl", "-s", "--max-time", "60", GO_URL,
             "-H", f"Authorization: Bearer {GO_KEY}",
             "-H", "Content-Type: application/json",
             "-H", f"x-opencode-session: {session}",
             "-A", "funnier-party/1.0",
             "-d", body],
            capture_output=True, text=True, timeout=70)
    except Exception as e:
        raise RuntimeError(f"Go request failed: {e}")
    try:
        resp = json.loads(proc.stdout or "{}")
    except Exception:
        raise RuntimeError(f"Go bad response: {(proc.stdout or '')[:200]}")
    if "choices" not in resp:
        raise RuntimeError(f"Go error: {(proc.stdout or '')[:200]}")
    content = resp["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        event = json.loads(content)
    except Exception:
        # Truncated analysis: one retry, then fail loudly (never guess).
        proc = _sp.run(
            ["curl", "-s", "--max-time", "60", GO_URL,
             "-H", f"Authorization: Bearer {GO_KEY}",
             "-H", "Content-Type: application/json",
             "-H", f"x-opencode-session: {session}",
             "-A", "funnier-party/1.0",
             "-d", body],
            capture_output=True, text=True, timeout=70)
        resp = json.loads(proc.stdout or "{}")
        if "choices" not in resp:
            raise RuntimeError(f"Go error: {(proc.stdout or '')[:200]}")
        content = resp["choices"][0]["message"]["content"].strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        event = json.loads(content)
    event.setdefault("joke_id", beat_id or "unknown")
    event.setdefault("beat_id", beat_id)
    event.setdefault("transcript", transcript)
    mechs = event.get("mechanism", [])
    if isinstance(mechs, str):
        mechs = [mechs]
    event["mechanism"] = [m for m in mechs if m in MECHANISMS]
    if not event["mechanism"]:
        event["mechanism"] = ["not_a_joke"]
    event.setdefault("confidence_in_interpretation", 0.5)
    event.setdefault("uncertainty_reason", "")
    event["model"] = GO_MODEL
    return event


TESTS = [
    {"name": "Ordinary factual sentence",
     "transcript": "The weather is nice today.", "expect": {"not_a_joke"}},
    {"name": "Clear setup and punchline",
     "transcript": "I told my therapist I was afraid of commitment. She said we should "
                   "schedule weekly sessions. I said, 'Don't rush me.'",
     "expect": {"misdirection", "setup_punchline"}},
    {"name": "Ralph contradicts identity",
     "transcript": "I'm an apex predator. I control thirteen bloodlines. Yesterday HR "
                   "told me I need to work on my people skills.",
     "character": {"name": "Ralph the Reptilian",
                   "identity": "corporate middle-manager who believes he is an alien overlord"},
     "expect": {"status_reversal", "identity_contradiction"}},
    {"name": "Ambiguous line",
     "transcript": "That's what she said.",
     "expect_uncertain": True},
]


def run_tests():
    passed = failed = 0
    for t in TESTS:
        print(f"\n{t['name']}:")
        try:
            ev = interpret_joke(t["transcript"], t.get("character"))
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1
            continue
        mechs = set(ev["mechanism"])
        conf = ev.get("confidence_in_interpretation", 0)
        print(f"  mechanism: {sorted(mechs)} | confidence: {conf}")
        if t.get("expect_uncertain"):
            ok = conf < 0.7 or mechs == {"not_a_joke"}
        else:
            ok = bool(mechs & t["expect"])
        print(f"  {'PASS' if ok else 'FAIL'} (expected one of {sorted(t.get('expect', {'low-confidence'}))})")
        passed, failed = passed + ok, failed + (not ok)
    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("transcript", nargs="?", default="")
    ap.add_argument("--character", default="")
    ap.add_argument("--earlier", default="")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()
    if args.test:
        sys.exit(run_tests())
    char = None
    if args.character:
        char = json.loads(Path(args.character).read_text())
    print(json.dumps(interpret_joke(args.transcript, char, args.earlier), indent=1))
