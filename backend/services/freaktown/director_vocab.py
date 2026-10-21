"""Per-character director vocabulary (Mutuals-pattern, house providers).

A director vocab names the ONLY legal staging words for one freak and
what each means, so any stager (authored beats, LLM director, reactor)
stays inside what the stage can actually perform:

  emotions: {name: acting hint}   e.g. "deadpan": "flat, dry punchline"
  tags:     {delivery tag: emotion}  [giggles] -> happy (synonyms)
  intense:  [peak-only emotions, capped per reply]
  gestures / cameras / registers: legal lists
  limits:   {cameras: n, intense: n} per reply

Pattern credit: mutuals-inc/character-harness extensions/director +
emotion-tags (Apache-2.0). Their runtime is not adopted (paid providers
+ Kaigen player); the vocab contract is — it fits the POG_FACE_V1
intent world and our beat bus unchanged.

Stdlib only. Pure functions + one JSON loader. Never raises on bad
vocab: validate() reports errors, loading falls back to empty.
"""

import json
import re

TAG_RE = re.compile(r"^\s*\[([a-zA-Z][a-zA-Z ,_'\-]*)\]")


def load_vocab(path):
    """Load director.json. Returns (vocab dict, errors list). Never raises."""
    try:
        with open(path) as f:
            doc = json.load(f)
    except Exception as e:
        return empty_vocab(), ["unreadable: %s" % (e,)]
    return normalize_vocab(doc)


def empty_vocab():
    return {"emotions": {}, "tags": {}, "intense": [],
            "gestures": [], "cameras": [], "registers": [],
            "limits": {"cameras": 1, "intense": 2}}


def normalize_vocab(doc):
    """Coerce a loaded dict to the vocab shape + validation errors."""
    errors = []
    if not isinstance(doc, dict):
        return empty_vocab(), ["vocab must be a JSON object"]
    v = empty_vocab()
    emo = doc.get("emotions", {})
    if isinstance(emo, dict):
        v["emotions"] = {str(k): str(x) for k, x in emo.items()}
    else:
        errors.append("emotions must be a map")
    tags = doc.get("tags", {})
    if isinstance(tags, dict):
        v["tags"] = {str(k).lower(): str(x) for k, x in tags.items()}
    else:
        errors.append("tags must be a map")
    for key in ("intense", "gestures", "cameras", "registers"):
        val = doc.get(key, [])
        if isinstance(val, list):
            v[key] = [str(x) for x in val]
        else:
            errors.append("%s must be a list" % key)
    lim = doc.get("limits", {})
    if isinstance(lim, dict):
        for k in ("cameras", "intense"):
            try:
                v["limits"][k] = max(0, int(lim.get(k, v["limits"][k])))
            except Exception:
                errors.append("limits.%s must be an int" % k)
    # warn (not error): tags pointing outside the emotion set do nothing
    # on stage — same honesty rule as their check().
    known = set(v["emotions"])
    for tag, emo_name in v["tags"].items():
        if emo_name not in known:
            errors.append("tag [%s] maps to unknown emotion %r" % (
                tag, emo_name))
    return v, errors


def emotion_for_tag(tag, vocab):
    """Delivery-tag synonym -> emotion word, or None. Exact match,
    casefolded. No guessing."""
    try:
        return (vocab or {}).get("tags", {}).get(str(tag).lower())
    except Exception:
        return None


def opening_tag(text):
    """[tag] opener of a beat line, or None."""
    try:
        m = TAG_RE.match(str(text or ""))
    except Exception:
        return None
    return m.group(1).strip().lower() if m else None


def beat_emotion(beat_text, authored, vocab):
    """Resolve a beat's face: [tag] opener via synonym map wins (fast,
    no model — the emotion-tags pattern), else the authored expression,
    else None (stage stays procedural)."""
    tag = opening_tag(beat_text)
    if tag:
        emo = emotion_for_tag(tag, vocab)
        if emo:
            return emo
    if authored:
        return str(authored)
    return None


class Budget:
    """Per-reply spend tracker: intense emotions + cameras are capped,
    gestures sad-path to 'none' past budget. Mirrors their limits."""

    def __init__(self, vocab):
        try:
            lim = (vocab or {}).get("limits", {})
            self.max_cameras = int(lim.get("cameras", 1))
            self.max_intense = int(lim.get("intense", 2))
            self.intense = set((vocab or {}).get("intense", []))
        except Exception:
            self.max_cameras, self.max_intense, self.intense = 1, 2, set()
        self.cameras = 0
        self.intense_used = 0
        self.gestures = 0

    def allow_camera(self):
        if self.cameras < self.max_cameras:
            self.cameras += 1
            return True
        return False

    def allow_emotion(self, emotion):
        if emotion in self.intense:
            if self.intense_used < self.max_intense:
                self.intense_used += 1
                return True
            return False
        return True

    def allow_gesture(self):
        self.gestures += 1
        return True
