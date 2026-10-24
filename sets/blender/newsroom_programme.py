"""Newsroom programme: script -> the programme clock (pure Python, no bpy, no network).

    script   JSON {"show"?, "date"?, "title"?, "lines": [{speaker, text, kind: open|tee|body|close, story}],
             "stories"?: [{title, source}]}  (the Goodnight engine's 02_script/script.json works as is; story titles
             and sources are read from the tee lines "First: <title>. From <source>." when "stories" is absent)
             or plain text, one read per line, tagged:  [open] ... / [tee] ... / [body] ... / [close] ...
             with "## <title> | <source>" starting a story and "# <title>" naming the episode.
    reads    consecutive open (or close) lines are ONE read (one TTS wav), like the engine's rundown

layout(reads, durations, words, script, show) puts the reads on the programme clock: the intro sting, then each read
with the show's gaps (open -> first tee 1.6 s, tee -> body 0.9 s, story -> story 1.6 s, the sign-off), then the outro.
It returns the programme the director (newsroom_cameras.direct) and the bake (newsroom_episode.py) read:

    lines        [{id, kind, story, text, start_ms, end_ms, words: [{word, start_ms, end_ms}]}]
    cards        wall card schedule [{t_ms, card}]: title over the intro, ambient art under the first read, each
                 story's headline from just before its tee, ambient between stories, the sign-off card at the close
                 (the bake still swaps a cropped headline to ambient)
    lowers       lower thirds [{t_ms, dur_ms, kind: name|story, title, sub}]
    moods        [{t_ms, dur_ms, emotion, intensity}] from the read's kind and the show's tone
    stings       [{t_ms, kind: open|close, dur_ms}] for audiopost
"""
import json, pathlib, re

TEE = re.compile(r"^(?i:first|second|third|fourth|fifth|next|finally|and finally|also|then)\s*:\s*(.+)\.\s+From\s+(.+?)\.?\s*$",
                 re.DOTALL)


def load_script(path):
    p = pathlib.Path(path)
    txt = p.read_text()
    if p.suffix.lower() == ".json":
        s = json.loads(txt)
    else:
        s = {"lines": [], "stories": []}
        story, kind = None, "body"
        for raw in txt.splitlines():
            ln = raw.strip()
            if not ln:
                continue
            if ln.startswith("# "):
                s["title"] = ln[2:].strip()
                continue
            if ln.startswith("## "):
                t, _, src = ln[3:].partition("|")
                s["stories"].append({"title": t.strip(), "source": src.strip()})
                story = len(s["stories"]) - 1
                continue
            m = re.match(r"^\[(open|tee|body|close)\]\s*(.*)$", ln, re.I)
            if m:
                kind, ln = m.group(1).lower(), m.group(2)
            s["lines"].append({"speaker": "anchor", "text": ln, "kind": kind,
                               "story": None if kind in ("open", "close") else story})
    s.setdefault("stories", [])
    for ln in s["lines"]:
        if ln.get("kind") == "tee" and ln.get("story") is not None:
            k = ln["story"]
            while len(s["stories"]) <= k:
                s["stories"].append({})
            if not s["stories"][k].get("title"):
                m = TEE.match(ln["text"].strip())
                if m:
                    s["stories"][k] = {"title": m.group(1).strip(), "source": m.group(2).strip()}
                else:
                    s["stories"][k] = {"title": ln["text"].split(":", 1)[-1].strip(), "source": ""}
    return s


def reads(script):
    """Merge consecutive open (or close) lines into one read (one TTS wav each): [{id, kind, story, text}]."""
    out = []
    for ln in script["lines"]:
        kind, story = ln.get("kind", "body"), ln.get("story")
        if out and out[-1]["kind"] == kind and out[-1]["story"] == story and kind in ("open", "close"):
            out[-1]["text"] += " " + ln["text"].strip()
            continue
        tag = "open-ritual" if kind == "open" else "close-ritual" if kind == "close" else f"s{(story or 0) + 1}"
        n = sum(1 for r in out if r["id"].split("#")[0] == tag) + 1
        out.append({"id": f"{tag}#{n}", "kind": kind, "story": story, "text": ln["text"].strip()})
    return out


GAPS = {("intro", "open"): 0, ("open", "tee"): 1600, ("tee", "body"): 900, ("body", "tee"): 1600,
        ("body", "close"): 1600, ("open", "close"): 1200, ("close", "close"): 500, ("open", "open"): 500,
        ("body", "body"): 700}


def layout(rds, durations_ms, words, script, show, intro_ms=6000, outro_ms=5000):
    """Put reads on the programme clock. durations_ms[id] = wav length; words[id] = measured words (read clock)."""
    t = intro_ms
    lines = []
    prev = "intro"
    for r in rds:
        t += GAPS.get((prev, r["kind"]), 1000)
        d = int(durations_ms[r["id"]])
        ws = [{"word": w["word"], "start_ms": t + int(w["start_ms"]), "end_ms": t + int(w["end_ms"])} for w in words.get(r["id"], [])]
        end = ws[-1]["end_ms"] if ws else t + d
        lines.append({**r, "start_ms": t, "end_ms": end, "wav_ms": d, "words": ws})
        t = t + d
        prev = r["kind"]
    dur = t + outro_ms
    stories = script.get("stories", [])
    brand = show.get("brand", {})
    tone = show.get("tone", {})
    cards = [{"t_ms": 0, "card": "title"}]
    lowers, moods = [], []
    named = False
    for i, ln in enumerate(lines):
        if ln["kind"] == "open" and not named:
            named = True
            cards.append({"t_ms": ln["start_ms"] + 2500, "card": "ambient"})
            lowers.append({"t_ms": ln["start_ms"] + 1200, "dur_ms": 4200, "kind": "name",
                           "title": brand.get("anchor_name", "The night desk"), "sub": brand.get("title", "")})
        if ln["kind"] == "tee" and ln["story"] is not None:
            cards.append({"t_ms": max(0, ln["start_ms"] - 700), "card": f"story{ln['story']}"})
        if ln["kind"] == "body" and ln["story"] is not None:
            st = stories[ln["story"]] if ln["story"] < len(stories) else {}
            lowers.append({"t_ms": ln["start_ms"] + 800, "dur_ms": 5200, "kind": "story",
                           "title": st.get("title", ""), "sub": st.get("source", "")})
            nxt = lines[i + 1] if i + 1 < len(lines) else None
            if nxt is None or nxt["kind"] != "body":
                cards.append({"t_ms": ln["end_ms"] + 500, "card": "ambient"})
        if ln["kind"] == "close" and (i == 0 or lines[i - 1]["kind"] != "close"):
            cards.append({"t_ms": max(0, ln["start_ms"] - 600), "card": "signoff"})
        emo = {"open": tone.get("open", ("happy", 0.45)), "tee": tone.get("tee", ("relaxed", 0.5)),
               "body": tone.get("body", ("relaxed", 0.35)), "close": tone.get("close", ("happy", 0.6))}[ln["kind"]]
        moods.append({"t_ms": ln["start_ms"], "dur_ms": ln["end_ms"] - ln["start_ms"], "emotion": emo[0], "intensity": emo[1]})
    cards.append({"t_ms": dur - outro_ms + 600, "card": "title"})
    cards.sort(key=lambda c: c["t_ms"])
    stings = [{"t_ms": 0, "kind": "open", "dur_ms": intro_ms}, {"t_ms": dur - outro_ms - 200, "kind": "close", "dur_ms": outro_ms}]
    return {"duration_ms": dur, "intro_ms": intro_ms, "outro_ms": outro_ms, "lines": lines, "cards": cards,
            "lowers": lowers, "moods": moods, "stings": stings, "stories": stories, "show": show.get("id"),
            "title": script.get("title") or brand.get("title", ""), "date": script.get("date", "")}


def audiopost_plan(prog):
    """The audiopost plan.json for this programme (seconds, programme clock)."""
    return {"duration_s": prog["duration_ms"] / 1000,
            "lines": [{"id": ln["id"], "start": ln["start_ms"] / 1000, "end": ln["end_ms"] / 1000,
                       "wav_end": (ln["start_ms"] + ln["wav_ms"]) / 1000,
                       "words": [{"word": w["word"], "start": w["start_ms"] / 1000, "end": w["end_ms"] / 1000} for w in ln["words"]]}
                      for ln in prog["lines"]],
            "story_starts": [ln["start_ms"] / 1000 for ln in prog["lines"] if ln["kind"] == "tee"],
            "stings": [{"t": s["t_ms"] / 1000, "kind": s["kind"], "dur": s["dur_ms"] / 1000} for s in prog["stings"]],
            "music": {"bed_from": prog["intro_ms"] / 1000 - 1.0, "bed_to": (prog["duration_ms"] - prog["outro_ms"]) / 1000}}
