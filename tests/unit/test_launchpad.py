"""Unit tests for the launchpad layer: clips, reputation, pot, tickets."""

import uuid

import pytest


# ── Clip planner ─────────────────────────────────────────────────────

class TestClipPlanner:
    def test_best_window_finds_peak(self):
        from backend.services.clips import LaughBucket, find_best_window

        buckets = [
            LaughBucket(start_ms=0, laugh_events=2),
            LaughBucket(start_ms=5000, laugh_events=30),
            LaughBucket(start_ms=10000, laugh_events=25),
            LaughBucket(start_ms=40000, laugh_events=3),
        ]
        start, end, laughs = find_best_window(buckets, 20_000)
        assert start == 0  # window [0,20000) covers buckets 0+5000+10000
        assert end == 20_000
        assert laughs == 57  # 2 + 30 + 25 in window

    def test_best_window_empty(self):
        from backend.services.clips import find_best_window

        assert find_best_window([], 20_000) == (0, 20_000, 0)

    def test_best_window_prefers_breadth_on_tie(self):
        from backend.services.clips import LaughBucket, find_best_window

        buckets = [
            LaughBucket(start_ms=0, laugh_events=10, unique_laughers=1),
            LaughBucket(start_ms=30000, laugh_events=10, unique_laughers=8),
        ]
        start, _, _ = find_best_window(buckets, 5_000)
        assert start == 30000

    def test_peak_moment(self):
        from backend.services.clips import LaughBucket, peak_moment

        buckets = [
            LaughBucket(start_ms=0, laugh_events=2),
            LaughBucket(start_ms=17000, laugh_events=40),
            LaughBucket(start_ms=30000, laugh_events=5),
        ]
        assert peak_moment(buckets) == 17000
        assert peak_moment([]) == 0

    def test_tiktok_plan_clears_one_minute(self):
        from backend.services.clips import tiktok_plan, TIKTOK_MIN_MS, TIKTOK_MAX_MS

        # 60s set → 2000 + 60000 + 3000 = 65000, in range, no pad
        plan = tiktok_plan(60_000)
        assert plan["total_ms"] == 65_000
        assert plan["pad_ms"] == 0

        # Short set gets tail-padded to 63s, set untouched
        plan = tiktok_plan(30_000)
        assert plan["total_ms"] == TIKTOK_MIN_MS
        assert plan["set_ms"] == 30_000
        assert plan["pad_ms"] == TIKTOK_MIN_MS - (2000 + 30_000 + 3000)

        # Bounds hold across a sweep
        for set_ms in (0, 1000, 30_000, 59_400, 60_000, 70_000, 120_000):
            p = tiktok_plan(set_ms)
            assert p["set_ms"] == set_ms, "set is sacred"
            assert TIKTOK_MIN_MS <= p["total_ms"] <= TIKTOK_MAX_MS or set_ms > TIKTOK_MAX_MS

    def test_srt_format(self):
        from backend.services.clips import Word, words_to_srt

        words = [
            Word(word="Hello", start_ms=0, end_ms=400),
            Word(word="world", start_ms=400, end_ms=800),
        ]
        srt = words_to_srt(words)
        assert srt.startswith("1\n00:00:00,000 --> 00:00:00,800\nHello world")
        assert words_to_srt([]) == ""

    def test_full_package(self):
        from backend.services.clips import (
            LaughBucket, Word, plan_package, ffmpeg_cut_list, SCHEMA_VERSION,
        )

        buckets = [LaughBucket(start_ms=i * 1000, laugh_events=1 if i < 30 else 5) for i in range(60)]
        words = [Word(word=f"w{i}", start_ms=i * 500, end_ms=(i + 1) * 500) for i in range(120)]
        pkg = plan_package(
            performance_id="perf_1",
            character_slug="martin-lamp",
            episode_id="ep_1",
            duration_ms=60_000,
            buckets=buckets,
            words=words,
            score_reveal_ms=(60_000, 75_000),
            ella_roast_ms=(75_000, 95_000),
        )
        d = pkg.to_dict()
        assert d["version"] == SCHEMA_VERSION
        names = [s["name"] for s in d["segments"]]
        assert names == [
            "full-set-16x9.mp4", "full-set-9x16.mp4",
            "best-20s.mp4", "best-40s.mp4",
            "score-reveal.mp4", "ella-roast.mp4",
        ]
        # 9x16 full set clears the minute
        nine = next(s for s in d["segments"] if s["name"] == "full-set-9x16.mp4")
        assert 63_000 <= nine["duration_ms"] <= 75_000
        # 20s window is exactly 20s
        b20 = next(s for s in d["segments"] if s["name"] == "best-20s.mp4")
        assert b20["duration_ms"] == 20_000
        assert d["captions_srt"]
        assert len(d["captions_json"]) == 120

        cmds = ffmpeg_cut_list(pkg, "/rec/ep1.mp4", "/out")
        assert len(cmds) == 7  # 6 segments + thumbnail
        assert all(c.startswith("ffmpeg") for c in cmds)
        assert "martin-lamp-best-20s.mp4" in cmds[2]


# ── Reputation ───────────────────────────────────────────────────────

class TestReputation:
    def test_creator_code_format(self):
        from backend.services.reputation import creator_code

        uid = uuid.uuid4()
        code = creator_code(uid)
        assert code.startswith("creator_")
        assert len(code) == len("creator_XXXX")
        assert code == creator_code(uid)  # deterministic
        assert code == creator_code(str(uid))  # str/UUID agree
        assert creator_code(uuid.uuid4()) != code  # opaque per user

    def test_character_record(self):
        from backend.services.reputation import AppearanceResult, aggregate_character

        results = [
            AppearanceResult("a1", "c1", "KEEP", 8.7, 9.2, 0.81, False),
            AppearanceResult("a2", "c1", "CUT", 4.1, 5.0, 0.2, False),
            AppearanceResult("a3", "c1", "KEEP", 7.5, 8.0, 0.6, True),
            AppearanceResult("a4", "c2", "KEEP", 9.0, 9.0, 0.9, False),
        ]
        rec = aggregate_character("c1", results)
        assert rec.record == "2-1"
        assert rec.appearances == 3
        assert rec.best_ella == 8.7
        assert rec.best_stream == 9.2
        assert rec.best_laugh_share == 0.81
        assert rec.golden_tickets == 1
        assert rec.is_regular is True  # 3 apps, 2 wins

        rec2 = aggregate_character("c2", results)
        assert rec2.record == "1-0"
        assert rec2.is_regular is False  # only 1 appearance

    def test_leaderboard_order(self):
        from backend.services.reputation import (
            AppearanceResult, aggregate_character, leaderboard,
        )

        def rec(cid, wins, losses, best):
            rs = (
                [AppearanceResult(f"{cid}-w{i}", cid, "KEEP", best, best, 0.5) for i in range(wins)]
                + [AppearanceResult(f"{cid}-l{i}", cid, "CUT", 3.0, 3.0, 0.1) for i in range(losses)]
            )
            return aggregate_character(cid, rs)

        a = rec("a", 3, 2, 7.0)  # 3 wins
        b = rec("b", 2, 0, 9.5)  # 2 wins, best Ella
        c = rec("c", 2, 5, 6.0)  # 2 wins, more losses
        ranked = leaderboard([c, a, b])
        assert [r.comedian_id for r in ranked] == ["a", "b", "c"]

    def test_ticket_numbering(self):
        from backend.services.reputation import next_ticket_number, ticket_label

        assert next_ticket_number([]) == 1
        assert next_ticket_number([1, 2, 3]) == 4
        label = ticket_label(4, "ep19")
        assert "004" in label and "Ella" in label

    def test_creator_stats(self):
        from backend.services.reputation import (
            AppearanceResult, aggregate_character, aggregate_creator, creator_code,
        )

        uid = uuid.uuid4()
        r1 = aggregate_character("c1", [
            AppearanceResult("a1", "c1", "KEEP", 8.0, 8.0, 0.5, True),
            AppearanceResult("a2", "c1", "KEEP", 7.0, 7.0, 0.4, False),
        ])
        r2 = aggregate_character("c2", [
            AppearanceResult("a3", "c2", "CUT", 4.0, 4.0, 0.1, False),
        ])
        stats = aggregate_creator(uid, ["c1", "c2"], {"c1": r1, "c2": r2})
        assert stats.creator_code == creator_code(uid)
        assert stats.freaks_created == 2
        assert stats.total_wins == 2
        assert stats.golden_tickets == 1
        assert stats.best_character_id == "c1"


# ── Pot ──────────────────────────────────────────────────────────────

class TestPot:
    def test_pot_totals(self):
        from backend.services.pot import pot_total, pot_total_for_episode

        events = [
            {"type": "pot.contribution", "episode_id": "ep1",
             "payload": {"amount_cents": 1782, "source": "platform_revenue"}},
            {"type": "pot.contribution", "episode_id": "ep1",
             "payload": {"amount_cents": 2000, "source": "sponsor"}},
            {"type": "pot.contribution", "episode_id": "ep2",
             "payload": {"amount_cents": 500, "source": "manual"}},
            {"type": "show.phase", "episode_id": "ep1", "payload": {}},
            {"type": "pot.contribution", "episode_id": "ep1",
             "payload": {"amount_cents": -100, "source": "manual"}},  # ignored
        ]
        assert pot_total(events) == 4282
        assert pot_total_for_episode(events, "ep1") == 3782
        assert pot_total_for_episode(events, "ep9") == 0

    def test_validation(self):
        from backend.services.pot import validate_contribution

        validate_contribution(100, "sponsor")
        with pytest.raises(ValueError):
            validate_contribution(0, "sponsor")
        with pytest.raises(ValueError):
            validate_contribution(-5, "sponsor")
        with pytest.raises(ValueError):
            validate_contribution(100, "tokenomics")

    def test_format(self):
        from backend.services.pot import format_usd

        assert format_usd(3782) == "$37.82"
        assert format_usd(0) == "$0.00"
