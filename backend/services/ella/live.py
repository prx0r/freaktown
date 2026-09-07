"""EllaLive session manager — Tier 1 persistent presence.

The manager owns session lifecycle: sense in (structured perception,
never raw audio transcription — we already know the script, WAV, beats
and pauses), actions out, interruption on high-priority events (a $500
donation mid-sentence STOPS her current line — presence, not playback).

Transports implement LiveTransport. FakeLiveTransport is real enough
for tests and dev (records senses, replays scripted actions, honors
interrupt). Provider transports (OpenAI Realtime, Gemini Live) land
with API keys — their config descriptors live here so wiring them is
mechanical, not architectural:

  ELLA_LIVE_PROVIDER=openai-realtime   # or gemini-live
  ELLA_LIVE_MODEL=gpt-realtime-2.1     # or gemini-3.1-flash-live-preview
  OPENAI_API_KEY=... / GEMINI_API_KEY=...

Voice routing (decided, not yet live):
  OpenAI path → custom Ella voice inside the realtime model, OR
  text brain → ElevenLabs Flash websocket (~75ms), edge-tts stays
  free/dev/fallback. Never block the session on voice choice.
"""

from dataclasses import dataclass, field


PROVIDER_CONFIGS = {
    "openai-realtime": {
        "model_env": "ELLA_LIVE_MODEL",
        "default_model": "gpt-realtime-2.1",
        "key_env": "OPENAI_API_KEY",
        "notes": "native speech-to-speech, server+semantic VAD, interruption, tool calls",
    },
    "gemini-live": {
        "model_env": "ELLA_LIVE_MODEL",
        "default_model": "gemini-3.1-flash-live-preview",
        "key_env": "GEMINI_API_KEY",
        "notes": "persistent websocket, audio+text+function calling, 20-40ms chunks",
    },
}


class LiveTransport:
    """Realtime model transport interface."""

    async def connect(self) -> None:
        raise NotImplementedError

    async def send_sense(self, sense: dict) -> None:
        """Deliver structured perception (script/beats/reactions/pot)."""
        raise NotImplementedError

    async def interrupt(self) -> None:
        """Cancel the ongoing response + clear output buffer."""
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


@dataclass
class FakeLiveTransport(LiveTransport):
    """Test/dev transport: records senses, replays scripted actions."""

    senses: list[dict] = field(default_factory=list)
    scripted_actions: list[dict] = field(default_factory=list)
    interrupted: int = 0
    connected: bool = False
    on_action = None

    async def connect(self) -> None:
        self.connected = True

    async def send_sense(self, sense: dict) -> None:
        if not self.connected:
            raise RuntimeError("transport not connected")
        self.senses.append(sense)
        while self.scripted_actions:
            action = self.scripted_actions.pop(0)
            if self.on_action:
                self.on_action(action)

    async def interrupt(self) -> None:
        self.interrupted += 1

    async def close(self) -> None:
        self.connected = False


def provider_status(provider: str, env: dict | None = None) -> dict:
    """Report whether a live provider can start. No keys, no session."""
    import os

    env = env if env is not None else os.environ
    cfg = PROVIDER_CONFIGS.get(provider)
    if not cfg:
        return {"provider": provider, "ready": False, "reason": f"unknown provider: {provider}"}
    key = (env.get(cfg["key_env"]) or "").strip()
    if not key:
        return {"provider": provider, "ready": False,
                "reason": f"{cfg['key_env']} not configured"}
    return {"provider": provider, "ready": True,
            "model": env.get(cfg["model_env"]) or cfg["default_model"]}


class EllaLiveSession:
    """One persistent Ella presence for an episode."""

    # Sense shapes that interrupt her current line (presence > playback).
    INTERRUPT_TRIGGERS = ("big_tip", "wtf_spike")

    def __init__(self, episode_id: str, transport: LiveTransport | None = None):
        self.episode_id = episode_id
        self.transport = transport or FakeLiveTransport()
        self.actions: list[dict] = []
        self.senses_seen = 0
        self.transport.on_action = self._record_action

    async def start(self) -> None:
        await self.transport.connect()

    async def ingest_sense(self, sense: dict, triggers: list[str] | None = None) -> None:
        """Forward perception; interrupt on high-priority triggers."""
        self.senses_seen += 1
        await self.transport.send_sense(sense)
        for trigger in triggers or []:
            if trigger in self.INTERRUPT_TRIGGERS:
                await self.transport.interrupt()
                self.actions.append({
                    "type": "ella.action",
                    "trigger": trigger,
                    "action": "interrupt_line",
                    "source": "live-v1",
                })

    def _record_action(self, action: dict) -> None:
        self.actions.append({"source": "live-v1", **action})

    async def stop(self) -> None:
        await self.transport.close()
