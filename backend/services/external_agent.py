"""External agent interview controller — BYO-agent protocol.

Allows external agents to control a contestant during the interview.
The agent receives Ella's questions and responds on behalf of the character.

Protocol:
  1. Agent registers with episode + appearance
  2. Agent receives interview context (Ella's question, character info)
  3. Agent responds with character's dialogue
  4. Agent can also receive audience signals and adjust

Security:
  - Short-lived tokens scoped to one appearance
  - Rate limited
  - Cannot modify character or issue stage events
"""

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from backend.config import settings


@dataclass
class AgentConfig:
    """Configuration for an external agent endpoint."""
    endpoint_url: str  # https://my-agent.example.com/interview
    auth_header: str | None = None  # "Authorization: Bearer ..."
    timeout_ms: int = 5000
    max_retries: int = 2


@dataclass
class InterviewRequest:
    """What we send to the external agent."""
    appearance_id: str
    episode_id: str
    comedian_name: str
    character_deal: str
    character_facts: list[str]
    ella_question: str
    conversation_history: list[dict]
    audience_signal: str  # "moderate laughter", "huge laugh", "silence"
    turn_count: int


@dataclass
class InterviewResponse:
    """What the external agent returns."""
    text: str
    emotion: str | None = None
    gesture: str | None = None
    should_end: bool = False


class ExternalAgentController:
    """Controls a contestant via an external agent endpoint."""

    def __init__(self):
        self._tokens: dict[str, dict] = {}  # token -> {appearance_id, expires_at}

    def issue_token(self, appearance_id: str, episode_id: str) -> str:
        """Issue a short-lived token for an external agent."""
        token = f"agent_{uuid.uuid4().hex}"
        self._tokens[token] = {
            "appearance_id": appearance_id,
            "episode_id": episode_id,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
        return token

    def validate_token(self, token: str, appearance_id: str) -> bool:
        """Validate an agent token."""
        if token not in self._tokens:
            return False
        entry = self._tokens[token]
        if entry["expires_at"] < datetime.now(timezone.utc):
            del self._tokens[token]
            return False
        return entry["appearance_id"] == appearance_id

    async def get_response(
        self,
        config: AgentConfig,
        request: InterviewRequest,
    ) -> InterviewResponse:
        """Call the external agent endpoint to get a response."""

        payload = {
            "appearance_id": request.appearance_id,
            "episode_id": request.episode_id,
            "character": {
                "name": request.comedian_name,
                "deal": request.character_deal,
                "facts": request.character_facts,
            },
            "ella_question": request.ella_question,
            "conversation_history": request.conversation_history,
            "audience_signal": request.audience_signal,
            "turn_count": request.turn_count,
        }

        headers = {"Content-Type": "application/json"}
        if config.auth_header:
            headers["Authorization"] = config.auth_header

        try:
            async with httpx.AsyncClient(timeout=config.timeout_ms / 1000) as client:
                response = await client.post(
                    config.endpoint_url,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                return InterviewResponse(
                    text=data.get("text", ""),
                    emotion=data.get("emotion"),
                    gesture=data.get("gesture"),
                    should_end=data.get("should_end", False),
                )

        except httpx.TimeoutException:
            # Agent timed out — use fallback
            return InterviewResponse(
                text="...",
                emotion="confused",
                should_end=False,
            )
        except Exception as e:
            # Agent error — use fallback
            return InterviewResponse(
                text="[agent error]",
                emotion="error",
                should_end=True,
            )


# Singleton
external_agent_controller = ExternalAgentController()
