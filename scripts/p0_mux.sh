#!/bin/bash
# P0 mux: frames + wav (+srt sidecar) -> set.mp4 (faststart) + set.webm
# Prevents regression of the Oct-10 fixes (moov-at-end broke Firefox,
# mp4-only broke codeless browsers). No re-encode of pixels beyond the
# mezzanine: x264 CRF 23 for mp4, VP9 CRF 32 for webm.
set -euo pipefail
FRAMES=""; AUDIO=""; OUTDIR=""; FPS=24
while [ $# -gt 0 ]; do case "$1" in
  --frames) FRAMES="$2"; shift 2;;
  --audio) AUDIO="$2"; shift 2;;
  --outdir) OUTDIR="$2"; shift 2;;
  --fps) FPS="$2"; shift 2;;
  *) echo "usage: $0 --frames DIR --audio SET.wav --outdir DIR [--fps 24]"; exit 1;;
esac; done
[ -n "$FRAMES" ] && [ -n "$AUDIO" ] && [ -n "$OUTDIR" ] || { echo "missing args"; exit 1; }
mkdir -p "$OUTDIR"
# normalize Blender's f###.png names to zero-padded f%04d (overflow-safe)
python3 - "$FRAMES" <<'EOF'
import os, re, sys
d = sys.argv[1]
files = sorted((int(m.group(1)), f) for f in os.listdir(d) if (m := re.match(r"f(\d+)\.png$", f)))
for i, (n, f) in enumerate(files, 1):
    want = "f%04d.png" % i
    if f != want:
        os.rename(os.path.join(d, f), os.path.join(d, want))
print(len(files), "frames normalized")
EOF
ffmpeg -y -v error -framerate "$FPS" -i "$FRAMES/f%04d.png" -i "$AUDIO" \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -shortest -movflags +faststart "$OUTDIR/set.mp4"
ffmpeg -y -v error -i "$OUTDIR/set.mp4" \
  -c:v libvpx-vp9 -crf 32 -b:v 0 -cpu-used 4 -row-mt 1 \
  -c:a libopus -b:a 64k "$OUTDIR/set.webm"
python3 - "$OUTDIR" <<'EOF'
import sys
from pathlib import Path
d = Path(sys.argv[1])
for name in ("set.mp4", "set.webm"):
    b = (d / name).read_bytes()[:60000]
    moov, mdat = b.find(b"moov"), b.find(b"mdat")
    print(name, "moov:", moov, "OK" if (name.endswith(".webm") or 0 < moov < mdat) else "CHECK")
EOF
echo "muxed $OUTDIR/set.mp4 + set.webm"
