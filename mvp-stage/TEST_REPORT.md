# Test report

Validated locally with TTS disabled so the tests do not depend on network access.

## Unit tests

`FREAKTOWN_DISABLE_TTS=1 python -m unittest discover -s tests -v`

Result: **4/4 passed**.

Covered:

- reaction events are session-scoped
- timestamps are set-relative
- completed session JSON persists to disk
- counts and 5-second bins are derived correctly
- invalid reaction types are rejected
- frontend contract contains pinned three.ws runtime and reaction/completion endpoints

## Syntax checks

- `python -m py_compile web/server.py` — passed
- `node --check` on the inline frontend JavaScript — passed

## HTTP smoke test

Started the local server with `FREAKTOWN_DISABLE_TTS=1`, then exercised:

`GET /api/set` → `POST /api/start` → laugh → clap → `POST /api/complete`

Result: **passed**. The final JSON reported one laugh, one clap, correct 5-second bins, and persisted a completed session file.
