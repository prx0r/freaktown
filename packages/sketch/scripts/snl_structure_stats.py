#!/usr/bin/env python3
"""Derive aggregate SKETCH-SHOW STRUCTURE stats from public structured metadata.

Source: hhllcks/snldb (https://github.com/hhllcks/snldb), output/*.json — a
scrape of the episode/segment/appearance metadata published on
snlarchives.net. Only metadata is used (segment categories, order, which
performers appear, recurring-sketch ids). No scripts or transcripts are read,
downloaded or stored; no performer, character or sketch NAMES are written.

The raw files stay OUT of the repo (default /workspace/work/snldb, gitignored
pattern data/snldb/). Only the aggregate JSON below is committed:

    python3 packages/sketch/scripts/snl_structure_stats.py [--raw DIR] [--out FILE]
    # fetch the raw files first (≈9 MB):
    python3 packages/sketch/scripts/snl_structure_stats.py --fetch --raw /workspace/work/snldb

Output: packages/sketch/data/structure-stats.json (deterministic: sorted keys,
rounded numbers), consumed by packages/sketch/src/rundown.ts defaults.
"""
import argparse, json, os, statistics, sys, urllib.request
from collections import Counter, defaultdict

FILES = ["titles.json", "appearances.json", "episodes.json", "sketches.json"]
BASE = "https://raw.githubusercontent.com/hhllcks/snldb/master/output/"

# snldb category -> coarse segment type used by the sketch layer
COARSE = {
    "Cold Opening": "cold_open",
    "Monologue": "monologue",
    "Sketch": "sketch", "Show": "sketch", "Game Show": "sketch", "Award Show": "sketch", "Musical Sketch": "sketch",
    "Weekend Update": "news_desk", "Saturday Night News": "news_desk", "SNL Newsbreak": "news_desk",
    "Film": "filmed", "Commercial": "filmed", "Cartoon": "filmed", "Music Video": "filmed",
    "Musical Performance": "music", "Guest Performance": "music",
    "Goodnights": "closer",
}
SKETCHLIKE = {"cold_open", "sketch", "filmed", "news_desk"}


def load(raw, name):
    with open(os.path.join(raw, name), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (k - lo), 2)


def r(x, n=3):
    return round(x, n) if isinstance(x, float) else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="/workspace/work/snldb")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "structure-stats.json"))
    ap.add_argument("--fetch", action="store_true", help="download the raw snldb files into --raw first")
    a = ap.parse_args()
    if a.fetch:
        os.makedirs(a.raw, exist_ok=True)
        for f in FILES:
            urllib.request.urlretrieve(BASE + f, os.path.join(a.raw, f))
    for f in FILES:
        if not os.path.exists(os.path.join(a.raw, f)):
            sys.exit(f"missing {f} in {a.raw} (run with --fetch)")

    titles = load(a.raw, "titles.json")
    apps = load(a.raw, "appearances.json")
    eps = load(a.raw, "episodes.json")
    season = {e["epid"]: e["sid"] for e in eps}

    by_ep = defaultdict(list)
    for t in titles:
        by_ep[t["epid"]].append(t)
    for v in by_ep.values():
        v.sort(key=lambda t: t["order"])

    performers = defaultdict(set)  # tid -> distinct performers (cast + host + cameo + guest + filmed)
    for x in apps:
        if x.get("capacity") in ("cast", "host", "cameo", "guest", "filmed", "other"):
            performers[x["tid"]].add(x["aid"])

    # ── segment mix + order ───────────────────────────────────────────
    cat_counts = Counter(t["category"] for t in titles)
    coarse_counts = Counter(COARSE.get(t["category"], "other") for t in titles)
    seg_per_ep, sketchlike_per_ep, sketch_per_ep, filmed_per_ep = [], [], [], []
    rel_pos = defaultdict(list)
    first_is_cold, last_is_closer, mono_second, update_after_mid = 0, 0, 0, 0
    n_eps = 0
    sequences = Counter()
    for epid, segs in by_ep.items():
        types = [COARSE.get(t["category"], "other") for t in segs]
        if len(types) < 5:
            continue
        n_eps += 1
        seg_per_ep.append(len(types))
        sketchlike_per_ep.append(sum(1 for x in types if x in SKETCHLIKE))
        sketch_per_ep.append(types.count("sketch"))
        filmed_per_ep.append(types.count("filmed"))
        n = len(types)
        for i, x in enumerate(types):
            rel_pos[x].append(i / (n - 1))
        first_is_cold += types[0] == "cold_open"
        last_is_closer += types[-1] == "closer"
        no_music = [x for x in types if x not in ("music", "other")]
        mono_second += len(no_music) > 1 and no_music[0] == "cold_open" and no_music[1] == "monologue"
        if "news_desk" in types:
            update_after_mid += types.index("news_desk") / (n - 1) >= 0.4
        # compressed rundown (music + misc dropped, consecutive sketches collapsed to one token with a count)
        comp = []
        for x in no_music:
            if comp and comp[-1][0] == x and x in ("sketch", "filmed"):
                comp[-1][1] += 1
            else:
                comp.append([x, 1])
        sequences[" > ".join(c[0] for c in comp)] += 1

    # ── typical rundown: modal coarse type per normalised slot (10 slots, music dropped) ──
    slots = defaultdict(Counter)
    for epid, segs in by_ep.items():
        types = [COARSE.get(t["category"], "other") for t in segs if COARSE.get(t["category"]) not in ("music", None)]
        if len(types) < 5:
            continue
        for i, x in enumerate(types):
            slots[min(9, int(10 * i / len(types)))][x] += 1
    typical = []
    for s in range(10):
        tot = sum(slots[s].values())
        top = slots[s].most_common(2)
        typical.append({"slot": s, "type": top[0][0], "share": r(top[0][1] / tot), "runner_up": top[1][0] if len(top) > 1 else None})

    # ── cast size per segment type ────────────────────────────────────
    cast_size = defaultdict(list)
    for t in titles:
        c = COARSE.get(t["category"], "other")
        k = len(performers.get(t["tid"], ()))
        if k:
            cast_size[c].append(k)
    def dist(xs):
        h = Counter(min(x, 10) for x in xs)
        return {
            "n": len(xs), "mean": r(statistics.mean(xs), 2), "median": statistics.median(xs),
            "p25": q(xs, 0.25), "p75": q(xs, 0.75), "p90": q(xs, 0.9),
            "histogram_1_to_10plus": {str(i): r(h.get(i, 0) / len(xs)) for i in range(1, 11)},
        }
    cast_by_type = {k: dist(v) for k, v in sorted(cast_size.items()) if len(v) >= 30}

    # ── recurring-sketch share (titles linked to a recurring sketch id) ──
    rec = defaultdict(lambda: [0, 0])
    for t in titles:
        c = COARSE.get(t["category"], "other")
        if c not in ("sketch", "cold_open", "filmed", "news_desk"):
            continue
        dec = None
        sid = season.get(t["epid"])
        if sid:
            dec = f"seasons_{((sid - 1) // 10) * 10 + 1}-{((sid - 1) // 10) * 10 + 10}"
        for key in (c, "all_sketchlike", dec):
            if key:
                rec[key][1] += 1
                rec[key][0] += t.get("skid") is not None
    recurring = {k: {"recurring": v[0], "total": v[1], "share": r(v[0] / v[1])} for k, v in sorted(rec.items())}
    reuse = Counter(t["skid"] for t in titles if t.get("skid"))
    rec_installments = sorted(reuse.values())

    out = {
        "source": {
            "dataset": "hhllcks/snldb output/*.json (episodes, titles, appearances, sketches)",
            "dataset_url": "https://github.com/hhllcks/snldb",
            "upstream": "snlarchives.net (episode/segment metadata)",
            "note": "Aggregate counts only. No scripts/transcripts, no performer/character/sketch names. Regenerate with packages/sketch/scripts/snl_structure_stats.py.",
            "seasons": [min(season.values()), max(season.values())],
            "episodes": n_eps,
            "segments": len(titles),
        },
        "segment_categories": {k: v for k, v in sorted(cat_counts.items())},
        "coarse_types": {k: v for k, v in sorted(coarse_counts.items())},
        "coarse_map": COARSE,
        "per_episode": {
            "segments": {"median": statistics.median(seg_per_ep), "p25": q(seg_per_ep, 0.25), "p75": q(seg_per_ep, 0.75)},
            "sketchlike_segments": {"median": statistics.median(sketchlike_per_ep), "p25": q(sketchlike_per_ep, 0.25), "p75": q(sketchlike_per_ep, 0.75)},
            "live_sketches": {"median": statistics.median(sketch_per_ep), "p25": q(sketch_per_ep, 0.25), "p75": q(sketch_per_ep, 0.75)},
            "filmed_pieces": {"median": statistics.median(filmed_per_ep), "p25": q(filmed_per_ep, 0.25), "p75": q(filmed_per_ep, 0.75)},
        },
        "order": {
            "first_segment_is_cold_open": r(first_is_cold / n_eps),
            "monologue_follows_cold_open": r(mono_second / n_eps),
            "last_segment_is_goodnights": r(last_is_closer / n_eps),
            "news_desk_in_back_half_share": r(update_after_mid / max(1, sum(1 for s in by_ep.values() if any(COARSE.get(t["category"]) == "news_desk" for t in s)))),
            "median_relative_position": {k: q(v, 0.5) for k, v in sorted(rel_pos.items()) if len(v) >= 30},
        },
        "typical_rundown_slots": typical,
        "top_rundown_shapes": [{"shape": s, "episodes": n} for s, n in sequences.most_common(5)],
        "cast_size_per_segment": cast_by_type,
        "recurring": recurring,
        "recurring_installments_per_sketch": {"sketches": len(rec_installments), "median": statistics.median(rec_installments), "p90": q(rec_installments, 0.9)},
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote", os.path.relpath(a.out), "episodes", n_eps)


if __name__ == "__main__":
    main()
