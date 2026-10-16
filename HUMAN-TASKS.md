# HUMAN TASKS — things only you can do (2026-09-12)

Nothing here costs money. Everything runs on free tiers; the standing rule
is no spend, ever. Work through top to bottom; each unblocks agent work.

## Keys and secrets (do these first)

- [ ] MiMo: all three pasted keys are VALID on OpenCode Go
  (`opencode.ai/zen/go/v1`, 37 models incl. `mimo-v2.5`) — my Xiaomi
  endpoint was wrong, keys were fine (a fourth key also valid). BUT both
  workspaces' monthly usage limits are hit (resets in ~2 and ~7 days;
  balance top-up = spend, your call).
  Provider hardcoded in `~/.config/opencode/opencode.jsonc` (correct
  endpoint, key via `{env:MIMO_API_KEY}`). Sim takes it via `MIMO_SEATS=`
  + `MIMO_API_KEY`. Run hermes-vs-mimo A/B after reset.

- [ ] Kaggle: attach a secret named exactly `HF_TOKEN` (value already in
  the vault under `main`) to BOTH kernels (`walkout-render-v1`,
  `qwen-bank-render-v1`), then hit Run on each. Without it both fail at
  model download — that is their current and only blocker.
- [ ] Hugging Face: click accept on the gated model pages for
  `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` (and `-Base`) and
  `stabilityai/stable-audio-open-1.0`, or downloads get refused.
- [ ] Rotate anything pasted in chat: the Cloudflare token + R2 pair (seen
  twice), the Atlas workspace key (revoke in the API Keys tab), the HF
  token (regenerate when convenient). Vault already holds clean copies
  (`KAGGLE_API_TOKEN`, `KAGGLE_USERNAME=priortrades`, `HF_TOKEN`).
- [ ] Atlas: export `animation_3.glb` (greet clip) to the stallshark bucket
  when it finishes — only 1 and 2 have landed so far.
- [ ] Still open from 09-11: GitHub PAT rotation + deploy key, vault
  `member` grant for opencode, LiveKit Cloud + Qwen/DashScope keys for
  Pogtown Phase 1 (see `~/pogtown/pogtown-mvp/docs/HANDOVER-2026-09-11.md`).

## Playtests (only your eyes count — ~10 minutes)

- [ ] Dad full body: `/r/dad-demo-001`, step back, arms out, record.
  Report: does the body follow? Are arms mirrored (your left drives his
  right)? Does an old phone chug?
- [ ] Badger framing: `/r/badger-002` — camera fix verification, fully in
  frame now?
- [ ] Revoice: any take → revoice link → Kokoro deep male voice. Compare
  against the old Guy voice.
- [ ] Reroll studio: same page — reroll a walkout, follow a perform-as link.
- [ ] Birthday run: record a take, save-video, send it to someone. Report
  what confused them.

## Decisions and pushes (yours alone)

- [ ] Push: `trial/avatar-flow` has ~2 days of uncommitted work (`app.py`,
  `tts_provider.py`, scripts, docs). Owner pushes — say the word.
- [ ] qp repo (`~/qp`, scaffolded 2026-09-12): define its purpose —
  current guess is agent-games arena (mafia sim + MCP bridge live in
  pogtown-mvp/scripts, may move there).
- [ ] Next build pick after playtests: clip playback polish, blind
  human-vs-agent game, or pog.pet landing.
- [ ] `chatgpt-right` judge seat rename (trademark) — still deferred.
- [ ] pog.pet: confirm DNS/registrar state when you want the landing built.
