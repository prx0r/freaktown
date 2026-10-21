"""Qwen Omni realtime reactor: ears + improv brain for the live room.

The reactor HEARS the room and emits face/gaze/gesture intents. It is
never lipsync: the mouth runs off its own audio (analyser or Rhubarb),
and this module only returns ReactionPolicy keys + optional tag lines.

Cost discipline (owner rule: no surprise spend):
  - Local VAD gate ($0) decides when a reaction window is worth opening.
  - Omni hears 2-4 s windows, not streams. Cooldowns bound the count.
  - Hard cap: MAX_WINDOWS_PER_SHOW windows per process lifetime.
  - Key from QWEN_API_KEY env only. Refuses to run without it; the key
    is never logged, stored, or written anywhere.

Stdlib only (socket/ssl/hashlib/base64/threading/json/struct).
Offline-testable: VAD classify, window gating, and transcript->event
mapping are pure functions (see test_face_voice.py).
"""

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import threading
import time
import uuid
from urllib.parse import urlparse

from .face_voice import ReactionPolicy

WS_URL = ("wss://ws-h6o7g3oq9mc7u24u.ap-southeast-1.maas.aliyuncs.com"
          "/api-ws/v1/realtime")
WS_MODEL = "qwen3.8-omni-flash-realtime"

# 16 kHz s16le mono in (what Omni expects), 24 kHz PCM out (mouth food).
IN_RATE = 16000
MAX_WINDOW_S = 4.0
WINDOW_COOLDOWN_S = 20.0
MAX_WINDOWS_PER_SHOW = 12

# Local VAD: shout-band RMS over 100 ms frames. Tunables, not truth.
FRAME_MS = 100
LAUGH_RMS = 900       # sustained mid-band chatter / laughter
SHOUT_RMS = 4000      # heckle-grade energy
ROOM_FLOOR = 150      # below this the room is "silent"


def frame_rms(pcm16):
    """RMS of one s16le mono frame. Pure stdlib, no numpy."""
    if not pcm16:
        return 0.0
    n = len(pcm16) // 2
    if n == 0:
        return 0.0
    fmt = "<%dh" % n
    try:
        samples = struct.unpack(fmt, pcm16[:n * 2])
    except Exception:
        return 0.0
    return (sum(s * s for s in samples) / n) ** 0.5


def classify_room(frames_rms, speech_hint=False):
    """Recent per-100ms RMS list -> crowd dict for ReactionPolicy, or None
    when nothing is worth reacting to. Pure function."""
    if not frames_rms:
        return None
    try:
        recent = [float(x) for x in frames_rms[-40:]]
    except Exception:
        return None
    if not recent:
        return None
    avg = sum(recent) / len(recent)
    peak = max(recent)
    if peak >= SHOUT_RMS and (speech_hint or peak >= SHOUT_RMS * 1.5):
        return {"level": min(1.0, peak / 8000.0), "speech": True,
                "sustained": False}
    if avg >= LAUGH_RMS and len([x for x in recent if x >= LAUGH_RMS]) >= 8:
        return {"level": min(1.0, avg / 4000.0), "speech": False,
                "sustained": len(recent) >= 20}
    if avg < ROOM_FLOOR:
        return {"level": 0.0, "speech": False, "sustained": False}
    return None


REACTOR_INSTRUCTIONS = (
    "You are the silent reactor for a puppet comedy show. You hear the "
    "live room for a few seconds. Reply with ONE JSON object only, no "
    "other text: {\"event\": one of room_laugh, pog_burst, applause, "
    "heckle, silence_after_punch, none; \"emotion\": what the room feels "
    "like (one word: happy, sad, angry, surprised, afraid, disgust, "
    "neutral, or null if nothing); \"intensity\": 0-1 how strongly, or "
    "null; \"tag\": an optional <8-word deadpan tag line for the puppet, "
    "or null}. Never break character as the reactor. Never output "
    "anything but the JSON object.")


class OmniReactor:
    """Owns the realtime session and the window budget. Thread-safe."""

    def __init__(self, api_key=None, ws_url=WS_URL, model=WS_MODEL,
                 character="A deadpan puppet comedian."):
        key = api_key or os.environ.get("QWEN_API_KEY", "")
        if not key:
            raise RuntimeError("QWEN_API_KEY env required; refusing to run")
        self._key = key
        self._url = ws_url
        self._model = model
        self._character = character
        self.policy = ReactionPolicy()
        self.windows_used = 0
        self._last_window = 0.0
        self._lock = threading.Lock()

    def window_allowed(self):
        with self._lock:
            if self.windows_used >= MAX_WINDOWS_PER_SHOW:
                return False
            return (time.time() - self._last_window) >= WINDOW_COOLDOWN_S

    def _mark_window(self):
        with self._lock:
            self.windows_used += 1
            self._last_window = time.time()

    # -- minimal RFC6455 client (stdlib) ---------------------------

    def _connect(self):
        u = urlparse(self._url)
        host, port = u.hostname, u.port or 443
        path = u.path or "/"
        if u.query:
            path += "?" + u.query
        raw = socket.create_connection((host, port), timeout=15)
        sock = ssl.create_default_context().wrap_socket(
            raw, server_hostname=host)
        nonce = base64.b64encode(os.urandom(16)).decode()
        req = (
            "GET %s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Authorization: Bearer %s\r\n\r\n"
            % (path, host, nonce, self._key))
        sock.sendall(req.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk:
                raise RuntimeError("websocket handshake: no response")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket handshake refused: "
                               + head.split(b"\r\n", 1)[0].decode("latin1"))
        return sock

    @staticmethod
    def _ws_send(sock, obj):
        # event_id is REQUIRED by the gateway (Model Studio Realtime API);
        # events without one are silently dropped.
        obj = dict(obj)
        obj.setdefault("event_id", "event_" + uuid.uuid4().hex[:16])
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        frame = bytes([0x81, 0x80 | len(data) if len(data) < 126 else 0x80 | 126])
        if len(data) >= 126:
            frame += struct.pack(">H", len(data))
        frame += mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        sock.sendall(frame)

    @staticmethod
    def _ws_recv(sock, timeout=30):
        sock.settimeout(timeout)
        hdr = sock.recv(2)
        if len(hdr) < 2:
            raise RuntimeError("websocket closed")
        ln = hdr[1] & 0x7F
        if ln == 126:
            ln = struct.unpack(">H", sock.recv(2))[0]
        elif ln == 127:
            ln = struct.unpack(">Q", sock.recv(8))[0]
        payload = b""
        while len(payload) < ln:
            chunk = sock.recv(ln - len(payload))
            if not chunk:
                raise RuntimeError("websocket closed mid-frame")
            payload += chunk
        return json.loads(payload.decode("utf-8", "replace"))

    def react_to_window(self, pcm16_mono, timeout=30):
        """Send one <=4 s room window, get the reaction dict.

        Returns {"event", "emotion", "intensity", "tag"} (any may be
        None). Opens the budget window first; network failures return
        all-None (the show goes on). Resolve to a face with
        face_voice.resolve_expression."""
        if not self.window_allowed():
            return {"event": None, "emotion": None, "intensity": None,
                    "tag": None}
        if not pcm16_mono or len(pcm16_mono) > int(IN_RATE * 2
                                                   * MAX_WINDOW_S):
            return {"event": None, "emotion": None, "intensity": None,
                    "tag": None}
        self._mark_window()
        try:
            return self._react_once(pcm16_mono, timeout)
        except Exception:
            return {"event": None, "emotion": None, "intensity": None,
                    "tag": None}

    def _react_once(self, pcm16_mono, timeout):
        sock = self._connect()
        try:
            # Model Studio session schema (NOT the OpenAI nesting):
            # voice is a name string; formats are session-level.
            # turn_detection omitted = manual commit mode.
            self._ws_send(sock, {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": (self._character + " "
                                     + REACTOR_INSTRUCTIONS),
                    "voice": "Tina",
                    "input_audio_format": "pcm",
                    "output_audio_format": "pcm"}})
            self._ws_recv(sock, timeout)  # session.updated
            b64 = base64.b64encode(pcm16_mono).decode()
            for i in range(0, len(b64), 4096):
                self._ws_send(sock, {
                    "type": "input_audio_buffer.append",
                    "audio": b64[i:i + 4096]})
            self._ws_send(sock, {"type": "input_audio_buffer.commit"})
            self._ws_send(sock, {"type": "response.create"})
            transcript = _collect_transcript(sock, timeout)
            reaction = _transcript_to_reaction("".join(transcript))
            if reaction["event"] is None:
                return {"event": None, "emotion": None, "intensity": None,
                        "tag": None}
            return reaction
        finally:
            try:
                sock.close()
            except Exception:
                pass


def _collect_transcript(sock, timeout):
    """Drain response deltas until done. Pure socket helper."""
    transcript = []
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            msg = OmniReactor._ws_recv(
                sock, max(1, deadline - time.time()))
        except Exception:
            break
        t = msg.get("type", "")
        if t in ("response.audio_transcript.delta",
                 "response.text.delta"):
            transcript.append(msg.get("delta", ""))
        elif t in ("response.done", "response.completed",
                   "error"):
            break
    return transcript


def _transcript_to_reaction(text):
    """Omni's JSON reply -> reaction dict. Strict: anything unparsable
    is all-None (local energy still drives the face)."""
    blank = {"event": None, "emotion": None, "intensity": None,
             "tag": None}
    try:
        obj = json.loads(str(text).strip())
    except Exception:
        return dict(blank)
    if not isinstance(obj, dict):
        return dict(blank)
    from .face_voice import REACTIONS
    out = dict(blank)
    if obj.get("event") in REACTIONS:
        out["event"] = obj["event"]
    emo = str(obj.get("emotion") or "").lower() or None
    if emo:
        out["emotion"] = emo
    try:
        if obj.get("intensity") is not None:
            out["intensity"] = max(0.0, min(1.0,
                                           float(obj["intensity"])))
    except Exception:
        pass
    tag = obj.get("tag")
    if isinstance(tag, str) and tag.strip():
        out["tag"] = tag.strip()[:80]
    return out


def _transcript_to_event(text):
    """Omni's JSON reply -> REACTIONS key. Strict: anything unparsable
    is None (local energy still drives the face)."""
    return _transcript_to_reaction(text)["event"]
