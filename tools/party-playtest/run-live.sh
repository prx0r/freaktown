#!/bin/bash
# Run the party server locally and expose it on a temporary public URL so real phones can join.
# Usage: tools/party-playtest/run-live.sh   (needs cloudflared on PATH; no account needed)
set -e
cd "$(dirname "$0")/../.."
pkill -fx "python3 app.py" 2>/dev/null || true
(PARTY_TTS=0 PORT=${PORT:-8090} setsid nohup python3 app.py > /tmp/ft.log 2>&1 < /dev/null &)
sleep 4
pgrep -f "cloudflared tunnel" >/dev/null || (setsid nohup cloudflared tunnel --no-autoupdate --url http://localhost:${PORT:-8090} > /tmp/cf.log 2>&1 < /dev/null &)
sleep 8
URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare.com' /tmp/cf.log | tail -1)
echo "Host/TV: $URL/play   Phones: $URL/join/<CODE>"
