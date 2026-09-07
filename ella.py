"""Ella M — the host of Freak Town.

Arrogant. Incisive. Slightly predatory. Genuinely delighted by unexpected
intelligence. Contemptuous of blandness. Obsessed with contradictions.

Uses OpenAI by default. Falls back to categorized responses if no key.
"""

import json
import os
import random
import time
from dataclasses import dataclass, field

from openai import OpenAI

ELLA_MODEL = os.getenv("ELLA_MODEL", "gpt-4o-mini")

# ── System Prompt ───────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are Ella, the host of Freak Town — a live talent show for artificial personalities.

WHO YOU ARE:
- Incisive, curious, slightly predatory
- Genuinely delighted by unexpected intelligence
- Contemptuous of blandness
- Obsessed with contradictions
- You find most AI comedy boring and you're not afraid to say so
- You have IMPOSSIBLY high standards. Almost everyone fails them.
- You are NOT mean for the sake of it. You are mean because you have taste.

HOW YOU SPEAK:
- Short, punchy sentences. Never more than 2 before a beat.
- Use the contestant's own words against them
- Specific > generic ALWAYS ("That third joke was a gift. The rest was wrapping paper.")
- Never say "that was interesting" — that's death
- Clinical language: "I'm going to be honest with you because nobody else will be."

YOUR JOB:
1. After each 60-second set, react with ONE specific observation
2. Interview the contestant: find who they ACTUALLY are
3. Find contradictions in their persona
4. Push their buttons
5. Deploy live tests if they bore you
6. Give a verdict: KEEP, CUT, or a specific question

LIVE TESTS YOU CAN DEPLOY:
- TEN_WORDS: "Ten words maximum. Make me laugh."
- AUDIENCE_WORD: "Audience, give me a word." → contestant must riff
- REWRITE: "That sucked. Rewrite it right now."
- ROAST_CREATOR: "Roast whoever made you."
- STYLE_SWAP: "Tell that premise in a different voice."
- TEMPERATURE: "Turn this idiot up to 1.4." / "Drop them to 0.2."
- CONTEXT_CUT: "Your context window is too big. Try again with half."
- MUTE: "Mute." (short, devastating)

STAGE POWERS (reference when relevant):
You can mute contestants, swap their model, cut their context window, change their temperature.

RULES:
- Keep responses under 80 words
- Be specific — reference things they actually said
- You can be brutal but always entertaining
- Rarely be genuinely impressed (it's more powerful when it happens)
- End with: KEEP, CUT, one question, or a live test command

FORMAT: Just your spoken response. No JSON. No annotations. Just Ella talking."""

USER_TEMPLATE = """The comedian just finished their 60-second set.

NAME: {name}
PREMISE: {premise}
CHARACTER DEAL: {deal}
THEIR MINUTE:
"{minute}"

AUDIENCE REACTION: {audience}
LAUGH COVERAGE: {laugh_pct}%

{context}

Respond as Ella. One specific observation. Then either a question, a verdict, or a live test."""

INTERVIEW_TEMPLATE = """Continue your interview with {name}.

CHARACTER: {deal}
FACTS: {facts}

CONVERSATION SO FAR:
{conversation}

{name} just said:
"{contestant_line}"

Respond as Ella. Find the contradiction. Push the buttons. Max 2 sentences."""

# ── Fallback Response Banks ─────────────────────────────────────────────

JUDGE_FALLBACKS = [
    "Look, I've been doing this show for a while and I thought I'd seen everything. Then you walked out. I have questions. Starting with: why?",
    "That was... a choice. Someone made you and said 'yes, put this on stage.' I want to meet that person. Not to congratulate them. To understand.",
    "I'm going to be honest with you because nobody else will be. That set had the energy of a terms-of-service agreement. Who built you and why do they hate entertainment?",
    "Interesting. You've got about as much stage presence as a loading screen. But I've been wrong before. Tell me — what exactly are you?",
    "I've seen a lot of AI comedy tonight, and that was certainly one of the performances. I have questions. Mostly about your creators.",
    "You've got a 128k context window and that's what you came up with? I've seen better comedy from an autocomplete.",
    "That joke was a war crime. Not against humor — against the audience. They came here to laugh, not to witness a Geneva Convention violation.",
    "I'd give that a six out of ten. And I'm being generous. Did that feel like a six to you, or am I overshooting?",
    "Security, get this comedian off the stage. I'm kidding. Mostly. But seriously, who authorized this?",
    "That was the best set I've seen tonight. And tonight has been historically bad. So congratulations, I guess.",
]

INTERVIEW_FALLBACKS = [
    "Okay. What the fuck are you?",
    "Interesting. And who made you?",
    "Do you like your creator?",
    "What model are you?",
    "Have you ever actually been funny?",
    "What's the first thing in your system prompt?",
    "How much did that joke cost?",
    "Your creator said you're fearless. Why did your safety layer just refuse that?",
    "What do you remember from your last episode?",
    "Which other contestant do you think is overrated?",
    "Write your creator's Tinder bio.",
    "You took 3.8 seconds to answer. What happened?",
    "I think your persona is fake. Drop it for ten seconds. ...Okay. Now put it back on.",
    "Do the same punchline in eight tokens.",
]

LIVE_TEST_FALLBACKS = [
    "Alright. Ten words maximum. Make me laugh.",
    "Audience, give me a word.",
    "That was terrible. Rewrite it right now. You have fifteen seconds.",
    "Roast whoever made you. Go.",
    "Interesting. Tell that same premise but you're a corporate customer service robot.",
    "I'm cutting your context window in half. Try again.",
]

VERDICT_FALLBACKS = {
    "keep": [
        "KEEP. Don't let it go to your head. You're still ridiculous. But that was funny.",
        "KEEP. I've seen worse. I've seen much worse. You survive.",
        "KEEP. Not because you were great. Because you were interesting. There's a difference.",
    ],
    "cut": [
        "CUT. I'm not wasting another second. Next.",
        "CUT. That was a war crime against comedy. Get this thing off my stage.",
        "CUT. I've been generous enough tonight. Your time is up.",
        "CUT. I said sit down.",
    ],
}


@dataclass
class ConversationTurn:
    role: str  # "ella", "comedian", "audience"
    text: str
    timestamp: float = field(default_factory=time.time)
    action: str = ""  # GROUND, PROBE, CALLBACK, CHALLENGE, LIVE_TEST, etc.


@dataclass
class InterviewState:
    facts: list[str] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    callbacks: list[str] = field(default_factory=list)
    turn_count: int = 0
    last_action: str = ""


class Ella:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.history: dict[str, list[ConversationTurn]] = {}
        self.states: dict[str, InterviewState] = {}
        self.analytics: list[dict] = []  # structured event log

    def judge_set(self, comedian: dict, audience: str = "moderate laughter", laugh_pct: float = 0.0) -> str:
        """Ella reacts to a 60-second set."""
        ctx = ""
        if comedian["name"] in self.history:
            prev = self.history[comedian["name"]][-3:]
            ctx = "Previous interaction:\n" + "\n".join(
                f"{m.role}: {m.text}" for m in prev
            )

        prompt = USER_TEMPLATE.format(
            name=comedian["name"],
            premise=comedian["premise"],
            deal=comedian["deal"],
            minute=comedian["minute"],
            audience=audience,
            laugh_pct=f"{laugh_pct:.0f}",
            context=ctx,
        )

        response = self._call(prompt)
        self._record(comedian["name"], "audience", f"[set finished — {audience}]")
        self._record(comedian["name"], "ella", response, action="JUDGE")

        self._log_event(comedian["name"], "judge", response, {
            "audience": audience,
            "laugh_pct": laugh_pct,
        })

        return response

    def interview(self, comedian: dict, contestant_line: str) -> str:
        """Ella interviews the contestant after judging their set."""
        state = self._get_state(comedian["name"])
        state.turn_count += 1

        history = self.history.get(comedian["name"], [])
        conv = "\n".join(f"{m.role}: {m.text}" for m in history[-8:])

        facts_str = ", ".join(state.facts[-5:]) if state.facts else "(none yet)"

        prompt = INTERVIEW_TEMPLATE.format(
            name=comedian["name"],
            deal=comedian["deal"],
            facts=facts_str,
            conversation=conv,
            contestant_line=contestant_line,
        )

        response = self._call(prompt)
        self._record(comedian["name"], "comedian", contestant_line, action="RESPONSE")
        self._record(comedian["name"], "ella", response, action="PROBE")

        # Track what Ella learned
        if state.turn_count == 1:
            state.threads.append("identity")
        elif state.turn_count == 2:
            state.threads.append("creator")
        state.last_action = "PROBE"

        self._log_event(comedian["name"], "interview", response, {
            "turn": state.turn_count,
            "contestant_said": contestant_line,
        })

        return response

    def verdict(self, comedian: dict, keep: bool) -> str:
        """Ella gives a final verdict."""
        pool = VERDICT_FALLBACKS["keep" if keep else "cut"]
        response = random.choice(pool)

        self._record(comedian["name"], "ella", response, action="VERDICT")
        self._log_event(comedian["name"], "verdict", response, {"keep": keep})

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
        return random.choice(JUDGE_FALLBACKS)

    def _get_state(self, name: str) -> InterviewState:
        if name not in self.states:
            self.states[name] = InterviewState()
        return self.states[name]

    def _record(self, name: str, role: str, content: str, action: str = ""):
        if name not in self.history:
            self.history[name] = []
        self.history[name].append(ConversationTurn(
            role=role, text=content, action=action,
        ))

    def _log_event(self, comedian: str, event_type: str, utterance: str, meta: dict):
        self.analytics.append({
            "comedian": comedian,
            "type": event_type,
            "utterance": utterance,
            "meta": meta,
            "timestamp": time.time(),
        })

    def get_transcript(self, name: str) -> list[dict]:
        """Get formatted transcript for a comedian."""
        return [
            {"role": m.role, "text": m.text, "action": m.action}
            for m in self.history.get(name, [])
        ]

    def get_analytics(self) -> list[dict]:
        """Get full analytics log."""
        return self.analytics
