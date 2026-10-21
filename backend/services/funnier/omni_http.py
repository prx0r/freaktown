"""Qwen Omni reactor over HTTPS (chat completions + input_audio).

Same job as omni_reactor.py (ears + improv brain -> REACTIONS key) but
through the OpenAI-compatible chat endpoint instead of the realtime
socket. Proven against the live Singapore endpoint; use it when the WS
path is unavailable. Discrete 2-4 s windows fit this transport: no
persistent connection, no idle timeouts, same cost discipline (local VAD
gates every call).

Key from QWEN_API_KEY env only. Base URL from QWEN_BASE_URL env or the
Singapore default below.
"""

import base64
import io
import json
import os
import urllib.request
import wave

from .face_voice import REACTIONS
from .omni_reactor import REACTOR_INSTRUCTIONS

BASE_URL = ("https://ws-h6o7g3oq9mc7u24u.ap-southeast-1.maas.aliyuncs.com")
MODEL = "qwen3.8-omni-flash"


def pcm_to_wav_bytes(pcm16_mono, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16_mono)
    return buf.getvalue()


def react_to_window(pcm16_mono, character="A deadpan puppet comedian.",
                    timeout=90, model=MODEL, base_url=None,
                    api_key=None):
    """Send one <=4 s room window, return the reaction dict.

    {"event", "emotion", "intensity", "tag"} (any may be None).
    Resolve to a face with face_voice.resolve_expression.
    Never raises; network/parse failures return all-None."""
    blank = {"event": None, "emotion": None, "intensity": None,
             "tag": None}
    key = api_key or os.environ.get("QWEN_API_KEY", "")
    if not key or not pcm16_mono:
        return dict(blank)
    base = (base_url or os.environ.get("QWEN_BASE_URL", "") or BASE_URL)
    wav_b64 = base64.b64encode(pcm_to_wav_bytes(pcm16_mono)).decode()
    body = {"model": model, "max_tokens": 120, "messages": [{
        "role": "user", "content": [
            {"type": "text", "text": (
                character + " " + REACTOR_INSTRUCTIONS)},
            {"type": "input_audio",
             "input_audio": {"data": "data:audio/wav;base64," + wav_b64, "format": "wav"}}]}]}
    req = urllib.request.Request(
        base.rstrip("/") + "/compatible-mode/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read().decode())
        text = (((resp.get("choices") or [{}])[0].get("message") or {})
                .get("content") or "")
        return _to_reaction(text)
    except Exception:
        return dict(blank)


def _to_reaction(text):
    """Model JSON -> reaction dict. Strict; unparsable is all-None."""
    blank = {"event": None, "emotion": None, "intensity": None,
             "tag": None}
    try:
        obj = json.loads(str(text).strip())
    except Exception:
        return dict(blank)
    if not isinstance(obj, dict):
        return dict(blank)
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


def _to_event(text):
    return _to_reaction(text)["event"]
