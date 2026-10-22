# audiopost — studio post for synthetic voices

Deterministic, seeded, parameterised post chain that makes a clean TTS read sound like a person
in a room: small-studio acoustics, off-axis mic drift, plosive/proximity moments, breaths in
alignment gaps, room tone, light foley (paper, chair, mug), a gentle broadcast chain (HPF, EQ,
de-ess, compression), an original procedural jingle + bed with ducking, and a −14 LUFS /
true-peak master. numpy + scipy + soundfile + ffmpeg. No samples, no network, no TTS.

```bash
cd packages/audiopost
python -m audiopost run --vo vo_dry.wav --plan plan.json --preset goodnight-studio --seed 7 --out post/
python -m audiopost run ... --set mic_drift.dip_db=3.0 --set foley.creak_prob=0.2   # override knobs
python -m audiopost measure post/master.wav        # LUFS-I, LRA, true peak (ffmpeg ebur128)
python -m audiopost dry --vo vo_dry.wav --out dry.wav   # A side of an A/B: loudness only
python tests/test_audiopost.py
```

`plan.json` carries the VO clock: lines (start/end + word timings), story starts (paper lands
in the gap before each), jingle cues and the bed span. Every stage is zero-phase or keeps its
direct path at sample 0, so measured word timings stay valid after post (sync gates hold).

Presets: `goodnight-studio` (subtle late-night desk), `standup-club` (bigger room, handheld
drift, no bed), `sketch-room` (medium room, more creaks), `dry` (everything off). The knobs
are documented in damn `engine/GOODNIGHT-ENGINE.md` §"Audio imperfection knobs".

Same seed + same inputs = byte-identical master. Change the seed for a different take.
