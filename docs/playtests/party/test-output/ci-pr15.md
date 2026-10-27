# CI on PR #15 (head 526a57c), run 40220512261 — one loop
| job | PR | main c3d2f4e (run 39678063529) |
|---|---|---|
| party (new) | success | n/a |
| contracts | success | success |
| python | failure: 9 failed, 134 passed (same 9 test_avatar.py failures) | failure: 9 failed, 85 passed |
| browser | failure (tests/e2e test_golden_show, pre-existing) | failure |
| formats | failure (scripts/freak_format.py missing, pre-existing) | failure |
No new failures vs main; +49 passing tests.
