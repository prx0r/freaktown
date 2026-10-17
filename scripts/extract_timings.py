#!/usr/bin/env python3
"""Measured beat timings from set audio ($0, ffmpeg silencedetect).

Speech segments between silences map 1:1 onto delivery beats in order.
Output: freaks/<slug>/timings.json [{start_ms, end_ms}]. The venue driver
prefers these over even-cadence when present.

  /usr/bin/python3 scripts/extract_timings.py <slug> [slug...]
"""
import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def segments(wav):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav),
                        "-af", "silencedetect=noise=-30dB:d=0.4",
                        "-f", "null", "-"],
                       capture_output=True, text=True)
    sil = []
    start = None
    for line in p.stderr.splitlines():
        if "silence_start" in line:
            start = float(line.split("silence_start:")[1].split()[0])
        elif "silence_end" in line and start is not None:
            end = float(line.split("silence_end:")[1].split()[0])
            sil.append((start, end))
            start = None
    segs, prev = [], 0.0
    for s, e in sil:
        if s - prev > 0.3:
            segs.append([round(prev * 1000), round(s * 1000)])
        prev = e
    return segs, sil


def main():
    for slug in sys.argv[1:]:
        d = BASE / "freaks" / slug
        beats = json.loads((d / "delivery.json").read_text())["beats"]
        segs, sil = segments(d / "set.wav")
        import wave
        w = wave.open(str(d / "set.wav"))
        total = int(w.getnframes() / w.getframerate() * 1000)
        # beat boundaries = the N-1 LONGEST silences (mid-beat breaths lose)
        n = len(beats)
        bounds = sorted(sorted(sil, key=lambda x: x[1] - x[0],
                               reverse=True)[:max(0, n - 1)])
        cuts, out, prev = [b[1] for b in bounds], [], 0.0
        for c in cuts + [total / 1000]:
            if c * 1000 - prev > 300:
                out.append({"start_ms": round(prev),
                            "end_ms": round(c * 1000)})
            prev = c * 1000
        print(f"{slug}: {len(sil)} silences → {len(out)} beats "
              f"(wanted {n})")
        while len(out) < n:
            last = out[-1]["end_ms"] if out else 0
            per = (total - last) / (n - len(out))
            out.append({"start_ms": round(last),
                        "end_ms": round(last + per)})
        (d / "timings.json").write_text(json.dumps(
            {"measured": True, "source": "ffmpeg silencedetect",
             "segments": out}, indent=2))
        print(f"  wrote timings.json ({len(out)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
