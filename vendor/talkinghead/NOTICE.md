# Vendored: TalkingHead lipsync-en.mjs (MIT)

Source: https://github.com/met4citizen/TalkingHead
File: `modules/lipsync-en.mjs` (English letter-to-sound -> Oculus visemes,
adapted from NRL Report 7948) vendored verbatim as
`vendor/talkinghead/lipsync-en.mjs`. Full MIT text in `LICENSE-MIT`.

Why vendored, not npm: the take pipeline runs offline inside the Python
bank (no node_modules on GPU boxes); one file, zero dependencies, and the
rules must never drift from what the stage consumes. If upstream fixes
the rules, re-vendor the file and re-run `tests/contract/test_visemes.py`.
