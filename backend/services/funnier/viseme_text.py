"""Text + measured word timings -> Oculus viseme timeline (TalkingHead-en).

The letter-to-sound rules live in ONE place: the vendored
vendor/talkinghead/lipsync-en.mjs (MIT, TalkingHead). This module only
shapes take data into its input and validates its output. Run anywhere
node exists; never invents visemes (empty words emit nothing).

Output is the TalkingHead speakAudio shape:
  {words, wtimes, wdurations, visemes, vtimes, vdurations}
which the stage consumes directly (MorphVisemePlayer) and the Blender
factory can bake.
"""

import json
import os
import subprocess

HERE = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
WRAPPER = os.path.join(HERE, "scripts", "th_visemes.mjs")


def timeline_to_words(timeline):
    """take timeline.json -> [{text, start_ms, end_ms}] word list.

    Timeline rows carry beat text + spans; words split evenly across the
    row span (the wrapper re-weights by viseme mass, so this is only a
    first split — measured TTS timings stay authoritative at row level)."""
    words = []
    try:
        rows = timeline if isinstance(timeline, list) else []
    except Exception:
        return []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text", "") or "").strip()
        if not text:
            continue
        try:
            start = int(row.get("start_ms", 0))
            end = int(row.get("end_ms", start))
        except Exception:
            continue
        if end <= start:
            continue
        tokens = text.split()
        if not tokens:
            continue
        per, cursor = (end - start) / len(tokens), start
        for tok in tokens:
            wlen = per
            words.append({"text": tok, "start_ms": int(cursor),
                          "end_ms": int(cursor + wlen)})
            cursor += wlen
    return words


def run_wrapper(words, node="node", wrapper=WRAPPER):
    """Run the node wrapper on a word list. Returns the viseme doc.
    Raises RuntimeError with stderr tail on failure (never silent)."""
    payload = json.dumps({"words": words})
    try:
        p = subprocess.run([node, wrapper], input=payload,
                           capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        raise RuntimeError("node not found (tried %r)" % node)
    except subprocess.TimeoutExpired:
        raise RuntimeError("th_visemes.mjs timed out")
    if p.returncode != 0:
        raise RuntimeError("th_visemes failed: " + (p.stderr or "")[-1000:])
    try:
        doc = json.loads(p.stdout)
    except Exception:
        raise RuntimeError("th_visemes emitted invalid JSON")
    _validate(doc)
    return doc


def _validate(doc):
    if not isinstance(doc, dict):
        raise RuntimeError("viseme doc not a dict")
    for k in ("words", "wtimes", "wdurations", "visemes", "vtimes",
              "vdurations"):
        if not isinstance(doc.get(k), list):
            raise RuntimeError("viseme doc missing " + k)
    n = len(doc["words"])
    if not (len(doc["wtimes"]) == len(doc["wdurations"]) == n):
        raise RuntimeError("word arrays disagree")
    m = len(doc["visemes"])
    if not (len(doc["vtimes"]) == len(doc["vdurations"]) == m):
        raise RuntimeError("viseme arrays disagree")
    last = -1
    for t in doc["vtimes"]:
        if int(t) < last:
            raise RuntimeError("viseme times not monotonic")
        last = int(t)


def build_take_visemes(timeline, node="node"):
    """timeline.json rows -> validated viseme doc. Pure except node."""
    return run_wrapper(timeline_to_words(timeline), node=node)
