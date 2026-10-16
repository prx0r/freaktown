#!/usr/bin/env python3
"""p0_learn: human evidence -> notebook facts + policy evidence drafts.

Reads data/p0/reactions.jsonl + data/p0/feedback.jsonl, and per set updates:
  <setdir>/notebook.json  objective_facts (measured only)
  <setdir>/policy.json    evidence row (observed rates; human_laughter set
                          only when >=1 eligible view, else null)

Never touches identity, arms, or interpretations. Dry run by default;
--apply writes. Run after every judging session.
"""
import argparse
import datetime
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "scripts"))
from p0_studio import _load_perfs, _timeline, _plan  # noqa: E402  (read-only reuse)


def read_log(path):
    rows = []
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    return rows


def summarize(set_id, reacts, feeds, timeline):
    # Audience-only: rehearsal presses are reported separately and never
    # enter rates or bits. Origin is client-claimed (unverified) until
    # session auth lands; rates divide by feedback-backed viewers only.
    aud = [r for r in reacts if r.get("set_id") == set_id and r.get("origin", "audience") == "audience"]
    reh = [r for r in reacts if r.get("set_id") == set_id and r.get("origin") == "rehearsal"]
    feeds = [f for f in feeds if f.get("set_id") == set_id]
    seen, deduped = set(), []
    for r in aud:
        key = (r.get("viewer"), r.get("beat_id"), r.get("kind"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    viewers = sorted({r.get("viewer") for r in deduped} | {f.get("viewer") for f in feeds})
    eligible = sorted({f.get("viewer") for f in feeds})
    pog_by_beat: dict = {}
    kinds: dict = {}
    for r in deduped:
        kinds[r.get("kind")] = kinds.get(r.get("kind"), 0) + 1
        if r.get("kind") == "POG":
            b = r.get("beat_id") or "between"
            pog_by_beat[b] = pog_by_beat.get(b, 0) + 1
    strong = sorted(b for b, n in pog_by_beat.items() if n >= 2)
    weak = sorted(b.get("beat_id") for b in timeline
                  if b.get("beat_id") not in pog_by_beat)
    verdicts: dict = {}
    for f in feeds:
        if f.get("verdict"):
            verdicts[f["verdict"]] = verdicts.get(f["verdict"], 0) + 1
    n_views = len(eligible)
    rate = round(sum(pog_by_beat.values()) / n_views, 3) if n_views else None
    has_evidence = bool(deduped) or bool(feeds)
    return {"presses": len(deduped), "rehearsal_presses": len(reh),
            "by_kind": kinds, "viewers": viewers,
            "eligible_views": n_views, "strong_bits": strong, "weak_bits": weak,
            "verdicts": verdicts, "pog_per_view": rate, "pog_by_beat": pog_by_beat,
            "has_evidence": has_evidence,
            "origin_note": "origins client-claimed, unverified; rehearsal excluded"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    reacts = read_log(os.path.join(HERE, "data", "p0", "reactions.jsonl"))
    feeds = read_log(os.path.join(HERE, "data", "p0", "feedback.jsonl"))
    today = datetime.date.today().isoformat()
    for p in _load_perfs():
        s = p["set"]
        d = os.path.join(HERE, p["dir"])
        tl = _timeline(p)
        plan = _plan(p)
        summ = summarize(s, reacts, feeds, tl)
        print(f"== {s}: presses={summ['presses']} views={summ['eligible_views']} "
              f"pog/view={summ['pog_per_view']} strong={summ['strong_bits']} verdicts={summ['verdicts']}")
        if not a.apply:
            continue
        nb_path = os.path.join(d, "notebook.json")
        nb = json.load(open(nb_path)) if os.path.exists(nb_path) else {"character_id": p.get("character")}
        nb["objective_facts"] = {
            "status": "human evidence" if summ["has_evidence"] else nb.get("objective_facts", {}).get("status", "rehearsal only, no audience"),
            "presses": summ["presses"], "eligible_views": summ["eligible_views"],
            "strong_bits": summ["strong_bits"], "weak_bits": summ["weak_bits"],
            "verdicts": summ["verdicts"], "origin_note": summ["origin_note"],
        }
        json.dump(nb, open(nb_path, "w"), indent=1)
        pol_path = os.path.join(d, "policy.json")
        if os.path.exists(pol_path):
            pol = json.load(open(pol_path))
            ev = pol.get("evidence", [])
            row = {"date": today, "set": s, "source": "p0_studio",
                   "mechanisms": list((plan.get("mechanisms") or {}).keys())
                   if isinstance(plan.get("mechanisms"), dict) else (plan.get("mechanisms") or []),
                   "observed": {"pog_per_view": summ["pog_per_view"],
                                "views": summ["eligible_views"],
                                "presses": summ["presses"],
                                "rehearsal_presses": summ["rehearsal_presses"],
                                "pog_by_beat": summ["pog_by_beat"]},
                   "human_laughter": summ["pog_per_view"],
                   "origin_note": summ["origin_note"],
                   "note": "p0 studio audience-claimed; critic QA is not laughter."}
            old = next((e for e in ev if e.get("set") == s and e.get("source") == "p0_studio"), None)
            if old is not None:
                ev[ev.index(old)] = row  # recompute, never freeze stale aggregates
            else:
                ev.append(row)
            pol["evidence"] = ev
            json.dump(pol, open(pol_path, "w"), indent=1)
    if not a.apply:
        print("(dry run — pass --apply to write notebooks/policies)")


if __name__ == "__main__":
    main()
