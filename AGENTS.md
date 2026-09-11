# AGENTS.md — freaktown

New agent: read `HANDOVER.md` first (current state + blockers), then
`docs/README.md`, then `docs/BOUNDARIES.md`. That order. Do not build until
you have read all three.

## Binding rules

1. **Secrets in vault/env, never in tree, never in chat.** Before every
   commit: `grep -rIlE "cfat_|ghp_|sk-[A-Za-z0-9]{10,}" --exclude-dir=.git .`
   must print nothing. Vault reads need `member` role; proxy role only wraps
   outbound calls.
2. **Never push.** Owner pushes. Commit locally only when asked.
3. **Check the site before claiming a deploy.** `curl` the public URL and the
   real routes (`/f/<slug>`, preload, studio) — a 200 on `/` proves nothing.
   A placeholder page is not a launch; say so loudly if that's all there is.
4. **Strangler, not rewrite.** `app.py`/`party.py` serve live traffic. Extract
   gradually, behavior identical. No second Studio/watch/party implementation
   (see `docs/BOUNDARIES.md` + `devplan.md` §2).
5. **Game truth lives in pogtown.** Never reimplement it here (`archive/` is
   the closed chapter). This repo consumes via adapter.
6. **Face/rig changes are additive.** New `face_profiles.py` profiles and
   manifest keys only; never rename/remove a field. Sniffer never invents a
   morph name that isn't in the bytes.
7. **Small diffs, tested each step.** Python: `pytest tests/contract
   tests/unit -q` (13 pre-existing env failures: espeak/fastapi/livekit —
   not yours unless you add a 14th). Party sim runs as script:
   `python3 test_party.py`, never under pytest.
8. **Kill by exact PID, never pattern-kill.** (`pkill -f app.py` matches your
   own shell. Read `/proc` cmdlines and kill the PID.)
9. **Background servers fight sandboxes.** Prefer in-process Flask test
   client for verification; use tunnels only for public demos.

## Where things are

`HANDOVER.md` (now) · `NORTHSTAR.md` (avatar doctrine) ·
`docs/TRIAL_STAGE1_PLAN.md` · `docs/HANDOFF_STABLE_AUDIO.md` ·
`docs/vendors/` + `docs/avataroptions.md` (renderer research) ·
`contracts/` (schema authority) · `archive/` (retired engine, read-only).
