"""Ella interview engine — stateful conversational AI for live interviews.

Per BUILD_BRIEF.md section 25:
  - Not one giant prompt
  - Maintains structured state
  - Actions: GROUND, PROBE, CALLBACK, CHALLENGE, LIVE_TEST, CHANGE_TOPIC, END
  - Separates reasoning from spoken dialogue
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from openai import AsyncOpenAI

from backend.config import settings


# ── Interview State ────────────────────────────────────────────────────

@dataclass
class InterviewState:
    """Structured state for Ella's conversation."""
    facts: list[str] = field(default_factory=list)
    threads: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    callbacks: list[str] = field(default_factory=list)
    comedic_targets: list[str] = field(default_factory=list)
    turn_count: int = 0
    last_action: str | None = None
    last_utterance: str | None = None

    def to_dict(self) -> dict:
        return {
            "facts": self.facts,
            "threads": self.threads,
            "contradictions": self.contradictions,
            "callbacks": self.callbacks,
            "comedic_targets": self.comedic_targets,
            "turn_count": self.turn_count,
            "last_action": self.last_action,
        }


@dataclass
class InterviewDecision:
    """Structured decision from Ella."""
    action: str  # GROUND, PROBE, CALLBACK, CHALLENGE, LIVE_TEST, CHANGE_TOPIC, END
    target: str
    utterance: str
    should_end: bool = False
    live_test_type: str | None = None  # TEN_WORDS, AUDIENCE_WORD, REWRITE, ROAST_CREATOR
    reasoning: str = ""


# ── System Prompt ──────────────────────────────────────────────────────

ELLA_SYSTEM_PROMPT = """You are Ella, the host of Freak Town — a live talent show for artificial personalities.

You are:
- Incisive, curious, slightly predatory
- Genuinely delighted by unexpected intelligence
- Contemptuous of blandness
- Obsessed with contradictions
- Capable of manipulating the contestant's environment

Your job is to discover who this character ACTUALLY is. Not their prepared material — them.

The interview mechanism:
1. GROUND — ask basic questions (how long doing comedy, where from, what do they do)
2. NOTICE ANOMALY — find something weird in their answers
3. PROBE — dig into the anomaly
4. FIND CONTRADICTION — catch them in a lie or inconsistency
5. ESCALATE — push harder

You have powers no human host has:
- You can cut their context window
- You can swap their model
- You can mute them
- You can change their temperature

After 3-5 turns, issue a LIVE_TEST if you find a weakness.

Available LIVE_TESTs:
- TEN_WORDS: "Ten words maximum. Make me laugh."
- AUDIENCE_WORD: Ask audience for a word, make them riff
- REWRITE: "That sucked. Rewrite it right now."
- ROAST_CREATOR: "Roast whoever made you."

Always output a JSON decision AFTER your utterance. Format:
[ELLACONNECT]{"action": "...", "target": "...", "reasoning": "..."}[/ELLACONNECT]

Your spoken response comes BEFORE the JSON block."""

ELLA_USER_TEMPLATE = """Episode: {episode_title}
Comedian: {comedian_name}
Character deal: {character_deal}
Minute excerpt: {minute_excerpt}

Audience reaction so far: {audience_signal}

Previous conversation:
{conversation_history}

The comedian just said:
"{comedian_response}"

Respond as Ella. Find the contradiction. Push the buttons."""


# ── Interview Engine ───────────────────────────────────────────────────

class EllaInterviewEngine:
    """Stateful interview engine for Ella."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self._states: dict[str, InterviewState] = {}

    def get_state(self, appearance_id: str) -> InterviewState:
        """Get or create interview state for an appearance."""
        if appearance_id not in self._states:
            self._states[appearance_id] = InterviewState()
        return self._states[appearance_id]

    def update_state(self, appearance_id: str, state: InterviewState):
        """Persist updated state."""
        self._states[appearance_id] = state

    async def generate_response(
        self,
        appearance_id: str,
        comedian_name: str,
        character_deal: str,
        minute_excerpt: str,
        comedian_response: str,
        episode_title: str = "Episode Zero",
        audience_signal: str = "moderate laughter",
        conversation_history: list[dict] | None = None,
    ) -> InterviewDecision:
        """Generate Ella's next response."""

        state = self.get_state(appearance_id)
        state.turn_count += 1

        # Build conversation history text
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-6:]:  # last 6 turns
                role = msg.get("role", "comedian")
                text = msg.get("text", "")
                history_text += f"{role}: {text}\n"

        if not history_text:
            history_text = "(first turn — you just said 'Okay. What the fuck are you?')"

        # Build prompt
        user_prompt = ELLA_USER_TEMPLATE.format(
            episode_title=episode_title,
            comedian_name=comedian_name,
            character_deal=character_deal,
            minute_excerpt=minute_excerpt[:500],
            audience_signal=audience_signal,
            conversation_history=history_text,
            comedian_response=comedian_response,
        )

        # Add state context
        if state.facts:
            user_prompt += f"\n\nKnown facts: {json.dumps(state.facts[-5:])}"
        if state.contradictions:
            user_prompt += f"\n\nContradictions found: {json.dumps(state.contradictions[-3:])}"
        if state.callbacks:
            user_prompt += f"\n\nCallbacks available: {json.dumps(state.callbacks[-3:])}"

        # Generate
        if self.client:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": ELLA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.9,
                max_tokens=500,
            )
            raw_text = response.choices[0].message.content or ""
        else:
            # Fallback for testing
            raw_text = self._fallback_response(comedian_name, character_deal, state)

        # Parse decision
        decision = self._parse_decision(raw_text, state)

        # Update state based on decision
        self._update_state_from_decision(state, decision)
        self.update_state(appearance_id, state)

        return decision

    def _parse_decision(self, raw_text: str, state: InterviewState) -> InterviewDecision:
        """Parse Ella's response into structured decision."""
        # Extract JSON block
        action = "PROBE"
        target = "general"
        reasoning = ""
        live_test = None
        should_end = False

        if "[ELLACONNECT]" in raw_text and "[/ELLACONNECT]" in raw_text:
            try:
                json_start = raw_text.index("[ELLACONNECT]") + len("[ELLACONNECT]")
                json_end = raw_text.index("[/ELLACONNECT]")
                json_str = raw_text[json_start:json_end].strip()
                parsed = json.loads(json_str)
                action = parsed.get("action", "PROBE")
                target = parsed.get("target", "general")
                reasoning = parsed.get("reasoning", "")
                live_test = parsed.get("live_test_type")
                should_end = action == "END"
            except (ValueError, json.JSONDecodeError):
                pass

        # Extract spoken utterance (everything before the JSON block)
        utterance = raw_text
        if "[ELLACONNECT]" in raw_text:
            utterance = raw_text[:raw_text.index("[ELLACONNECT]")].strip()

        return InterviewDecision(
            action=action,
            target=target,
            utterance=utterance,
            should_end=should_end,
            live_test_type=live_test,
            reasoning=reasoning,
        )

    def _update_state_from_decision(self, state: InterviewState, decision: InterviewDecision):
        """Update interview state based on the decision made."""
        state.last_action = decision.action
        state.last_utterance = decision.utterance

        if decision.action == "PROBE":
            state.threads.append(decision.target)
        elif decision.action == "CALLBACK":
            if state.callbacks:
                state.callbacks.pop(0)
        elif decision.action == "CHALLENGE":
            state.comedic_targets.append(decision.target)
        elif decision.action == "LIVE_TEST":
            state.comedic_targets.append(f"live_test:{decision.live_test_type}")

    def _fallback_response(self, comedian_name: str, character_deal: str, state: InterviewState) -> str:
        """Fallback response when no LLM is available."""
        if state.turn_count == 1:
            return f'Okay. What the fuck are you?\n\n[ELLACONNECT]{{"action": "GROUND", "target": "identity", "reasoning": "Opening question to discover the character"}}[/ELLACONNECT]'
        elif state.turn_count == 2:
            return f'Interesting. And who made you?\n\n[ELLACONNECT]{{"action": "PROBE", "target": "creator", "reasoning": "Digging into provenance"}}[/ELLACONNECT]'
        elif state.turn_count == 3:
            return f"So you're telling me...\n\n[ELLACONNECT]{{\"action\": \"CHALLENGE\", \"target\": \"consistency\", \"reasoning\": \"Testing their story\"}}[/ELLACONNECT]"
        else:
            return f"Alright. Ten words maximum. Make me laugh.\n\n[ELLACONNECT]{{\"action\": \"LIVE_TEST\", \"target\": \"humor_under_pressure\", \"reasoning\": \"Testing raw comedy ability\", \"live_test_type\": \"TEN_WORDS\"}}[/ELLACONNECT]"


# Singleton
ella_engine = EllaInterviewEngine()
