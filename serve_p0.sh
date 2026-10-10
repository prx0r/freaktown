#!/bin/bash
# P0 studio: watch sealed minutes, press POG, submit feedback.
#   ./serve_p0.sh              # :8091, background, health-checked
# Public (via figgsite tunnel /p0/*): https://www.pogtown.com/p0/
# Token is backend-held (data/.p0_token, gitignored) — never in URLs.
set -e
cd "$(dirname "$0")/.."
PORT="${1:-8091}"
if pgrep -f "scripts/p0_studio" >/dev/null; then
  echo "p0 studio already running (pid $(pgrep -f 'scripts/p0_studio' | head -n1))"
else
  nohup python3 scripts/p0_studio.py --port "$PORT" >/tmp/opencode/p0studio.log 2>&1 &
  sleep 3
fi
curl -s -m 10 -o /dev/null -w "local :$PORT %{http_code}\n" "http://127.0.0.1:$PORT/"
curl -s -m 20 -o /dev/null -w "public /p0/ %{http_code}\n" "https://www.pogtown.com/p0/"
echo "evidence: data/p0/reactions.jsonl data/p0/feedback.jsonl (gitignored)"
echo "learn:   python3 scripts/p0_learn.py [--apply]"
