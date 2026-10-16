# Stage 1 Trial Plan — prompt a character, stand up a minute

Status: PLAN ONLY. Nothing below is implemented. Each phase gates the next.

## Goal

A stranger can, on freak.town, with no account and no key of their own:
prompt → character → 60-second minute → voice audio → play → share `/f/` link
→ someone else hits YOUR TURN and gets a reply set. That is the whole trial.

## Non-goals (explicitly out)

Pogtown integration, Unreal, payments/potchain, new UI, avatar upgrades,
Ella realtime voice, Stable Audio local inference, native apps.

## Verified starting position (2026-09-11, code-read)

| Step | Powers it | Key? |
|---|---|---|
| Roll character | `_roll_character`, pure random (`app.py`) | No |
| Portrait | procedural PIL | No |
| Write the minute | `_cf_chat` → Cloudflare Workers AI, Llama-3.3-70B → Mistral-small → Llama-8B fallback | **YES — the single gate** |
| Voice audio | edge-tts (free) + local compose, espeak fallback | No |
| Walkout sting | procedural synth (fal optional) | No |
| Watch/share/respond | local bundles + JSONL | No |

Without `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` on the host,
`POST /api/respond` returns 502 "minute generation failed, retry" and the
trial dies at exactly one place. Everything else runs on what is deployed.

## Phase 0 — prove the chain locally (no keys, no live touch)

1. On a dev box, stub `_cf_chat` to return a fixed minute.
2. Run full loop: randomize → respond → beats → `set.wav` → play → reply.
3. Acceptance: audio plays, reply bundle validates, no 500s.
   Proves the CF key is the *only* gap before touching live.

## Phase 1 — light up live (one key, ~5 min human)

1. Human sets `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` on the live
   host (env, or the `/root/.agent-vault/vault.json` the code already reads).
   Never in chat, never in git.
2. One live loop by hand: randomize → respond with an idea → audio plays →
   reply generates → `/f/` link opens.
3. Acceptance: end-to-end 200s, audio audible, reply sensible.
   Any 502/500 here is the fix list (expected: tiny or empty).

## Phase 2 — trial guardrails (before sharing links)

1. Rate-limit `POST /api/respond` (only metered call in the loop; Workers AI
   free allowance covers a trial, but cap per-IP/day and alert on spend).
2. Invite-gate Studio creation; watch links stay public (viral loop needs it).
3. Concurrent-user check: live runs Flask dev server under systemd — fine for
   a trial, but load-test 10 parallel responds; if it falls over, put
   gunicorn (+2 workers) in front before widening, not after.
4. Rename the `chatgpt-right` judge seat persona to a parody-safe rival.
   Shipping a character literally named "ChatGPT" is a trademark fight with
   OpenAI we cannot afford — keep the seat, change the name.
5. Acceptance: 10 parallel loops green, spend dashboard checked daily week 1.

## Phase 3 — open trial

1. Seed 5 finished sets (so first visitors see a show, not an empty room).
2. Share `/f/` links; YOUR TURN loop is the retention mechanic — measure
   replies per watch, not watches.
3. Capture: which premises get replies, where users drop off, cost per
   finished minute. That data prices Phase 4 (Pogtown sealed bundles,
   payments).

## Risks

| Risk | Mitigation |
|---|---|
| CF bill surprise | per-IP caps + daily spend check week 1 |
| Flask dev server under trial load | 10-parallel test in Phase 2; gunicorn fallback ready |
| TTS sounds cheap | edge-tts is the trial voice; ElevenLabs oracle comes later, router already exists |
| Trademark (ChatGPT seat) | renamed in Phase 2, before any press/sharing |

## Rollback

Every phase is reversible: Phase 1 = unset two env vars; Phase 2 = remove
limits; Phase 3 = unpublish seed sets. No migrations, no schema changes,
no infra changes anywhere in this plan.
