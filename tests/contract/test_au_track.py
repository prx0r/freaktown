#!/usr/bin/env python3
"""AU prosody track: synthetic envelopes, no audio files needed."""

from backend.services.funnier.au_track import prosody_track, rms_envelope


def _sil(dur_ms, rate=16000, amp=0.0):
    return [amp] * int(rate * dur_ms / 1000)


def _tone(dur_ms, rate=16000, amp=0.5):
    import math
    n = int(rate * dur_ms / 1000)
    return [amp * math.sin(2 * math.pi * 220 * i / rate)
            for i in range(n)]


class TestEnvelope:
    def test_rms_scales(self):
        loud = rms_envelope(_tone(200, amp=0.8), 16000)
        quiet = rms_envelope(_tone(200, amp=0.2), 16000)
        assert sum(loud) / len(loud) > sum(quiet) / len(quiet)

    def test_empty(self):
        assert prosody_track([]) == []
        assert prosody_track(None) == []


class TestProsody:
    def test_accent_on_onset(self):
        samples = _sil(400) + _tone(400) + _sil(400)
        frames = prosody_track(samples)
        accents = [f["accent"] for f in frames]
        assert max(accents) >= 0.5, "onset must flash brows"
        # silence stays calm
        assert accents[0] == 0.0 and accents[-1] == 0.0

    def test_arousal_follows_loudness(self):
        loud = prosody_track(_tone(800, amp=0.8))
        quiet = prosody_track(_tone(800, amp=0.15))
        la = sum(f["arousal"] for f in loud) / len(loud)
        qa = sum(f["arousal"] for f in quiet) / len(quiet)
        assert la > qa

    def test_phrase_end_on_gap(self):
        samples = _tone(500) + _sil(600) + _tone(500)
        frames = prosody_track(samples)
        ends = [i for i, f in enumerate(frames) if f["phrase_end"]]
        assert len(ends) == 1, "one phrase boundary"
        # the flag lands right after the gap completes
        assert frames[ends[0]]["t_ms"] >= 500

    def test_no_false_phrase_in_speech(self):
        frames = prosody_track(_tone(1200, amp=0.5))
        assert all(f["phrase_end"] == 0 for f in frames)

    def test_frame_shape(self):
        frames = prosody_track(_tone(200))
        assert set(frames[0]) == {"t_ms", "accent", "arousal",
                                  "phrase_end"}
        assert [f["t_ms"] for f in frames] == \
            sorted(f["t_ms"] for f in frames)
