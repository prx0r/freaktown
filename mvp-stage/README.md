# Freak Town — one-minute stage MVP

A deliberately small prototype: a three.ws GLB avatar performs a ~60 second stand-up set, one human audience member presses **HAHA** and **CLAP**, and the app emits/persists structured timestamped JSON when the set ends.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python web/server.py
# open http://localhost:8080
```

If edge-tts is unavailable or the network call fails, the browser Speech Synthesis API is used automatically. For deterministic offline development:

```bash
FREAKTOWN_DISABLE_TTS=1 python web/server.py
```

## Output

Each completed run is saved to:

```text
web/data/sessions/<session_id>.json
```

The browser also exposes a **JSON** download button. Schema: `freaktown.set.v1`.

Important fields:

- `performer`, `set`, target/actual duration
- raw `events[]`: reaction type, set-relative timestamp, receive time, audience member ID
- `summary.reaction_counts`
- per-minute reaction rates
- first/last reaction timestamps
- 5-second reaction timeline and coverage

## API

- `GET /api/health`
- `GET /api/set`
- `POST /api/start`
- `POST /api/reaction`
- `POST /api/complete`
- `GET /api/session?id=<uuid>`

## Test

```bash
FREAKTOWN_DISABLE_TTS=1 python -m unittest discover -s tests -v
python -m py_compile web/server.py
```

The event shape is intentionally multi-user-ready now: `audience_member_id` is already part of every raw reaction event, even though the current UI is just one local viewer.
