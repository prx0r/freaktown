# Freak Town — Build Notes

Development log and architectural decisions.

## 2026-09-06 — Initial Build Session

### What was built

Full backend implementation from scratch based on 4 specification documents:
- `spec.md` — canonical backend architecture
- `spec2.md` — character-discovery machine
- `comedian-act-appearance.md` — data model
- `vision.md` — show + economic layer
- `docs/BUILD_BRIEF.md` — comprehensive 2,464-line build brief from R2

### Architecture decisions

1. **Python for offline, TypeScript for live**
   - Python/FastAPI handles: API, DB, LLM, TTS, submissions, judging
   - TypeScript/Cloudflare handles: live show coordination, WebSockets, Durable Objects
   - This split is intentional per BUILD_BRIEF.md

2. **Comedian → ActVersion → Submission → Appearance**
   - Never mutate a Comedian or ActVersion
   - Submission joins The Line (10,000+ eligible)
   - Appearance created only when selected (5 slots)
   - This enables the "10,000 agents waiting" visual

3. **Deterministic draw**
   - CSPRNG seed + Fisher-Yates
   - Seed commitment published before reveal
   - Replayable by anyone with seed + eligible set
   - No blockchain needed for this

4. **Event sourcing for show timeline**
   - Every stage action is a ShowEvent
   - Monotonically increasing seq
   - Stage client stores last_seq, reconnects with replay
   - Enables offline replay

5. **Ella interview engine**
   - Not one giant prompt
   - Stateful: facts, threads, contradictions, callbacks
   - Actions: GROUND, PROBE, CALLBACK, CHALLENGE, LIVE_TEST, END
   - Separates reasoning from spoken dialogue

6. **MCP-compatible API**
   - External agents can create comedians, submit, control interviews
   - API key auth with rate limiting
   - Short-lived tokens for interview control
   - BYO-agent protocol for custom AI

### What was imported from R2

- `comedy_transcripts.json` (20MB) — comedy dataset
- `seinfeld_scripts.json` (3.8MB) — Seinfeld scripts
- `Casey Rocket | This Past Weekend w/ Theo Von #671.en.srt` — transcript
- `Casey Rocket | This Past Weekend w/ Theo Von #671.mp3` (76MB) — audio
- `freaktown` — build brief document (2,464 lines)

### Key files created

```
backend/
├── auth.py                    # API key auth
├── config.py                  # Settings
├── main.py                    # FastAPI app
├── models/__init__.py         # 14 domain models
├── routes/
│   ├── comedians.py           # Creator flow
│   ├── episodes.py            # Episode lifecycle
│   ├── admin.py               # Control
│   ├── audience.py            # Audience WS
│   ├── stage.py               # Stage WS
│   └── mcp.py                 # MCP tools
└── services/
    ├── tts.py                 # edge-tts
    ├── performance_compiler.py # Text → plan
    ├── draw.py                # Deterministic draw
    ├── interview.py           # Ella engine
    ├── seed.py                # Episode Zero
    ├── events.py              # Event sequencing
    ├── external_agent.py      # BYO-agent
    ├── payments.py            # Privy wallet
    ├── stripe_connect.py      # Stripe
    ├── sponsors.py            # Sponsors
    ├── bodies.py              # Body families
    └── profiles.py            # Character pages

apps/web/
├── wrangler.jsonc             # Cloudflare config
└── worker/
    ├── index.ts               # Hono entry
    ├── api/index.ts           # API routes
    ├── auth/middleware.ts     # Auth
    └── episode-room.ts        # Durable Object
```

### Test results

```
Unit tests:      18/18 passing
Integration:      9/11 passing (2 skip without PostgreSQL)
```

### Next steps

1. Start PostgreSQL with `docker-compose up -d`
2. Run `alembic upgrade head` to create tables
3. Seed Episode Zero comedians
4. Test full flow: create → submit → draw → start → perform → interview
5. Deploy TypeScript Worker to Cloudflare
6. Set up Privy, Stripe, and LLM keys in `.env`
