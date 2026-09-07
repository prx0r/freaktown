#!/usr/bin/env python3
"""Ingest Kill Tony Archive data into Freak Town training format.

Reads the reprocessed JSON files from kill-tony-archive and produces:
1. A structured comedy dataset (JSONL)
2. Crowd reaction analysis
3. Tony scoring patterns
4. Material-to-outcome pairs for training
"""

import json
import os
from collections import Counter, defaultdict
from pathlib import Path

ARCHIVE_DIR = Path("/root/kill-tony-archive/data")
OUTPUT_DIR = Path("/root/freaktown/training_data")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Crowd reaction mapping ──────────────────────────────────────────────

REACTION_SCORES = {
    "silence": 0,
    "light": 1,
    "moderate": 2,
    "big_laughs": 3,
    "roaring": 4,
}

REACTION_LABELS = {
    0: "silence",
    1: "light chuckles",
    2: "moderate laughter",
    3: "big laughs",
    4: "roaring crowd",
}


def load_all_episodes():
    """Load all reprocessed episodes from the archive."""
    episodes = []
    for f in sorted(ARCHIVE_DIR.glob("reprocess_ep*_pass2.json")):
        with open(f) as fh:
            data = json.load(fh)
        episodes.append(data)
    return episodes


def ingest_sets(episodes):
    """Convert Kill Tony sets into Freak Town training format."""
    training_data = []

    for ep in episodes:
        ep_info = ep["episode"]
        ep_num = ep_info["episode_number"]
        guests = ep_info.get("guests", [])

        for s in ep.get("sets", []):
            # Map to Freak Town format
            record = {
                "source": "kill_tony_archive",
                "episode": ep_num,
                "set_number": s["set_number"],
                "comedian": s["comedian_name"],
                "status": s["status"],  # bucket_pull, regular, special_request
                "transcript": s["set_transcript"],
                "duration_sec": (s.get("set_end_seconds", 0) or 0) - (s.get("set_start_seconds", 0) or 0),
                "topics": s.get("topic_tags", []),
                "crowd_reaction": s.get("crowd_reaction", "unknown"),
                "crowd_score": REACTION_SCORES.get(s.get("crowd_reaction", ""), -1),
                "tony_score": s.get("tony_praise_level", 0),
                "golden_ticket": s.get("golden_ticket", False),
                "secret_show": s.get("invited_secret_show", False),
                "promoted": s.get("promoted_to_regular", False),
                "return_vote": s.get("sign_up_again", False),
                "joke_book": s.get("joke_book_size", "none"),
                "interview": s.get("interview_summary", ""),
                "age": s.get("disclosed_age"),
                "occupation": s.get("disclosed_occupation"),
                "location": s.get("disclosed_location"),
                "years_comedy": s.get("disclosed_years_doing_comedy"),
                "fun_facts": s.get("fun_facts", []),
                "guests": guests,
            }
            training_data.append(record)

    return training_data


def analyze_crowd_reactions(data):
    """Analyze what correlates with big laughs."""
    print("\n" + "=" * 60)
    print("  CROWD REACTION ANALYSIS")
    print("=" * 60)

    # Reaction distribution
    reactions = Counter(d["crowd_reaction"] for d in data)
    print("\nReaction Distribution:")
    for r in ["silence", "light", "moderate", "big_laughs", "roaring"]:
        count = reactions.get(r, 0)
        pct = count / len(data) * 100
        bar = "█" * int(pct / 2)
        print(f"  {r:<14} {count:>4} ({pct:5.1f}%) {bar}")

    # Tony score distribution
    print("\nTony Score Distribution:")
    scores = Counter(d["tony_score"] for d in data if d["tony_score"])
    for s in range(1, 6):
        count = scores.get(s, 0)
        pct = count / len([d for d in data if d["tony_score"]]) * 100
        bar = "█" * int(pct / 2)
        print(f"  {s}/5          {count:>4} ({pct:5.1f}%) {bar}")

    # Status vs crowd reaction
    print("\nStatus vs Crowd Reaction:")
    status_reaction = defaultdict(lambda: Counter())
    for d in data:
        status_reaction[d["status"]][d["crowd_reaction"]] += 1
    for status in ["bucket_pull", "regular", "special_request"]:
        if status in status_reaction:
            total = sum(status_reaction[status].values())
            big = status_reaction[status].get("big_laughs", 0) + status_reaction[status].get("roaring", 0)
            print(f"  {status:<20} {big}/{total} big laughs ({big/total*100:.0f}%)")

    # Topic vs crowd reaction
    print("\nTopics That Get Big Laughs:")
    topic_scores = defaultdict(list)
    for d in data:
        for t in d["topics"]:
            topic_scores[t].append(d["crowd_score"])
    topic_avg = {t: sum(s)/len(s) for t, s in topic_scores.items() if len(s) >= 3}
    for t, avg in sorted(topic_avg.items(), key=lambda x: -x[1])[:10]:
        print(f"  {t:<25} avg score: {avg:.2f} ({len(topic_scores[t])} sets)")

    # Golden ticket rate by reaction
    print("\nGolden Ticket Rate by Crowd Reaction:")
    for r in ["silence", "light", "moderate", "big_laughs", "roaring"]:
        subset = [d for d in data if d["crowd_reaction"] == r]
        if subset:
            gt = sum(1 for d in subset if d["golden_ticket"])
            print(f"  {r:<14} {gt}/{len(subset)} ({gt/len(subset)*100:.0f}%)")


def analyze_material_patterns(data):
    """Analyze what makes material successful."""
    print("\n" + "=" * 60)
    print("  MATERIAL PATTERN ANALYSIS")
    print("=" * 60)

    # Successful vs unsuccessful sets
    big_laugh_sets = [d for d in data if d["crowd_score"] >= 3]
    silence_sets = [d for d in data if d["crowd_score"] <= 1]

    print(f"\nBig laugh sets: {len(big_laugh_sets)}")
    print(f"Silence/light sets: {len(silence_sets)}")

    if big_laugh_sets:
        avg_len_big = sum(d["duration_sec"] for d in big_laugh_sets) / len(big_laugh_sets)
        avg_len_silence = sum(d["duration_sec"] for d in silence_sets) / max(1, len(silence_sets))
        print(f"Avg duration (big laughs): {avg_len_big:.0f}s")
        print(f"Avg duration (silence): {avg_len_silence:.0f}s")

    # Word count analysis
    big_words = [len(d["transcript"].split()) for d in big_laugh_sets]
    silence_words = [len(d["transcript"].split()) for d in silence_sets]
    if big_words:
        print(f"Avg word count (big laughs): {sum(big_words)/len(big_words):.0f}")
    if silence_words:
        print(f"Avg word count (silence): {sum(silence_words)/len(silence_words):.0f}")

    # Topic patterns
    print("\nTopic Frequency (big laughs):")
    big_topics = Counter()
    for d in big_laugh_sets:
        for t in d["topics"]:
            big_topics[t] += 1
    for t, c in big_topics.most_common(10):
        print(f"  {t:<25} {c}")


def save_training_data(data):
    """Save as JSONL for model training."""
    output_path = OUTPUT_DIR / "kill_tony_sets.jsonl"
    with open(output_path, "w") as f:
        for d in data:
            f.write(json.dumps(d) + "\n")
    print(f"\nSaved {len(data)} sets to {output_path}")

    # Also save a summary
    summary = {
        "total_episodes": len(set(d["episode"] for d in data)),
        "total_sets": len(data),
        "total_comedians": len(set(d["comedian"] for d in data)),
        "reaction_distribution": dict(Counter(d["crowd_reaction"] for d in data)),
        "avg_tony_score": sum(d["tony_score"] for d in data if d["tony_score"]) / max(1, len([d for d in data if d["tony_score"]])),
        "golden_tickets": sum(1 for d in data if d["golden_ticket"]),
        "topics": dict(Counter(t for d in data for t in d["topics"]).most_common(20)),
    }
    with open(OUTPUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved summary to {OUTPUT_DIR / 'summary.json'}")

    # Save material -> outcome pairs (the core training signal)
    pairs_path = OUTPUT_DIR / "material_outcome_pairs.jsonl"
    with open(pairs_path, "w") as f:
        for d in data:
            pair = {
                "material": d["transcript"][:500],
                "topics": d["topics"],
                "crowd_reaction": d["crowd_reaction"],
                "crowd_score": d["crowd_score"],
                "tony_score": d["tony_score"],
                "outcome": "hit" if d["crowd_score"] >= 3 else "miss",
            }
            f.write(json.dumps(pair) + "\n")
    print(f"Saved material-outcome pairs to {pairs_path}")


def main():
    print("Loading Kill Tony Archive data...")
    episodes = load_all_episodes()
    print(f"Loaded {len(episodes)} episodes")

    print("Ingesting sets...")
    data = ingest_sets(episodes)
    print(f"Ingested {len(data)} sets from {len(set(d['episode'] for d in data))} episodes")

    analyze_crowd_reactions(data)
    analyze_material_patterns(data)
    save_training_data(data)


if __name__ == "__main__":
    main()
