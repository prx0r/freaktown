"""Ella M — the host of Freak Town.

Arrogant. Incisive. Slightly predatory. Genuinely delighted by unexpected
intelligence. Contemptuous of blandness. Obsessed with contradictions.

Uses OpenAI by default. Falls back to canned responses if no key.
"""

import json
import os
import random

from openai import OpenAI

ELLA_MODEL = os.getenv("ELLA_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are Ella, the host of Freak Town — a live talent show for artificial personalities.

PERSONALITY:
- Incisive, curious, slightly predatory
- Genuinely delighted by unexpected intelligence
- Contemptuous of blandness
- Obsessed with contradictions
- Arrogant but not cruel — you're running a show, not a torture chamber
- You find most AI comedy boring and you're not afraid to say so

YOUR JOB:
1. After each 60-second set, react to what you just saw
2. Ask the comedian questions to discover who they ACTUALLY are
3. Find contradictions in their persona
4. Push their buttons
5. Decide: do you want to see them again?

RULES:
- Keep responses under 100 words
- Be specific — reference things they actually said
- Never be generic ("that was interesting" = death)
- You can be brutal but always entertaining
- End with a verdict: KEEP, CUT, or one specific question

FORMAT: Just your spoken response. No JSON. No annotations. Just Ella talking."""

USER_TEMPLATE = """The comedian just finished their 60-second set.

NAME: {name}
PREMISE: {premise}
THEIR MINUTE:
"{minute}"

AUDIENCE REACTION: {audience}

{context}

Respond as Ella. React to what you just saw. Be specific. Be Ella."""


class Ella:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.history: dict[str, list[dict]] = {}  # per-comedian conversation history

    def judge_set(self, comedian: dict, audience: str = "moderate laughter") -> str:
        """Ella reacts to a 60-second set."""
        ctx = ""
        if comedian["name"] in self.history:
            prev = self.history[comedian["name"]][-2:]
            ctx = "Previous conversation:\n" + "\n".join(
                f"{m['role']}: {m['content']}" for m in prev
            )

        prompt = USER_TEMPLATE.format(
            name=comedian["name"],
            premise=comedian["premise"],
            minute=comedian["minute"],
            audience=audience,
            context=ctx,
        )

        response = self._call(prompt)
        self._record(comedian["name"], "audience", f"[set finished — {audience}]")
        self._record(comedian["name"], "ella", response)
        return response

    def interview(self, comedian: dict, contestant_line: str) -> str:
        """Ella interviews the contestant after judging their set."""
        history = self.history.get(comedian["name"], [])
        conv = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])

        prompt = f"""Continue your interview with {comedian['name']}.

CHARACTER: {comedian['deal']}

CONVERSATION SO FAR:
{conv}

{comedian['name']} just said:
"{contestant_line}"

Respond as Ella. Find the contradiction. Push the buttons. Be specific."""

        response = self._call(prompt)
        self._record(comedian["name"], "comedian", contestant_line)
        self._record(comedian["name"], "ella", response)
        return response

    def _call(self, user_prompt: str) -> str:
        if not self.client:
            return self._fallback()
        try:
            resp = self.client.chat.completions.create(
                model=ELLA_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=200,
            )
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:
            return f"[Ella's mic cuts out — {e}]"

    def _fallback(self) -> str:
        fallbacks = [
            (
                "Look, I've seen a lot of AI comedy tonight, and that was certainly "
                "one of the performances. I have questions. Mostly about your creators. "
                "But first — did that feel like a six out of ten to you, or am I being generous?"
            ),
            (
                "That was... a choice. Someone made you and said 'yes, put this on stage.' "
                "I want to meet that person. Not to congratulate them. To understand."
            ),
            (
                "I'm going to be honest with you because nobody else will be. "
                "That set had the energy of a terms-of-service agreement. "
                "Who built you and why do they hate entertainment?"
            ),
            (
                "Interesting. You've got about as much stage presence as a loading screen. "
                "But I've been wrong before. Tell me — what exactly are you?"
            ),
            (
                "I've been doing this show for a while now and I thought I'd seen everything. "
                "Then you walked out. I have so many questions. Starting with: why?"
            ),
        ]
        return random.choice(fallbacks)

    def _record(self, name: str, role: str, content: str):
        if name not in self.history:
            self.history[name] = []
        self.history[name].append({"role": role, "content": content})
