# Freak Town — Problem Registry

Track of all issues, blockers, and technical debt discovered during development.

## Status Legend
- 🔴 BLOCKER — Cannot proceed without fixing
- 🟡 HIGH — Should fix before Episode Zero
- 🟢 MEDIUM — Fix before public launch
- ⚪ LOW — Known, acceptable for now

---

## Critical Issues

### 🔴 #1 — No PostgreSQL running in dev environment
**Discovered:** 2026-09-06
**Impact:** Integration tests skip, cannot test DB-dependent routes
**Fix:** Run `docker-compose up -d postgres redis` before testing
**Note:** All 18 unit tests pass. 9/11 integration tests pass (2 skip without DB)

### 🔴 #2 — Episode model has `max_contestants` but should be `max_appearances`
**Discovered:** 2026-09-06
**Impact:** Episode creation fails with `TypeError: 'max_contestants' is an invalid keyword argument`
**Fix:** Update `episodes.py` to use `max_appearances` or add the field back to model

### 🟡 #3 — Comedian name uniqueness is too strict
**Discovered:** 2026-09-06
**Impact:** Two users cannot create characters with the same display name
**Fix:** Per BUILD_BRIEF.md, name should NOT be globally unique. Only slug should be unique.

### 🟡 #4 — No `rev` or `version` field in ActVersion manifest hash
**Discovered:** 2026-09-06
**Impact:** Manifest hash doesn't include all immutable fields
**Fix:** Include `schemaVersion` and `revision` in the hash input

### 🟡 #5 — Event sequencing still uses hardcoded values in some places
**Discovered:** 2026-09-06
**Impact:** Some events may have duplicate seq values
**Fix:** Ensure ALL event emissions use `emit_event()` helper

---

## Architecture Issues

### 🟢 #6 — Python backend and TypeScript Worker are separate codebases
**Discovered:** 2026-09-06
**Impact:** Two runtime environments to maintain
**Fix:** Keep Python for offline research/evaluation, TypeScript for live runtime
**Note:** Per BUILD_BRIEF.md, this is intentional

### 🟢 #7 — No database migrations running
**Discovered:** 2026-09-06
**Impact:** Schema changes require manual SQL
**Fix:** Run `alembic upgrade head` when PG is available

### 🟢 #8 — In-memory crowd aggregation won't survive restarts
**Discovered:** 2026-09-06
**Impact:** Live show data lost on Worker restart
**Fix:** Durable Object storage persists important state before broadcasting

---

## Feature Gaps

### 🟢 #9 — No actual TTS generation in tests
**Discovered:** 2026-09-06
**Impact:** Cannot test audio generation pipeline
**Fix:** edge-tts is installed, need integration test with real generation

### 🟢 #10 — No Privy keys configured
**Discovered:** 2026-09-06
**Impact:** Auth middleware returns 500 without Privy config
**Fix:** Add `PRIVY_APP_ID` and `PRIVY_APP_SECRET` to `.env`

### 🟢 #11 — No Stripe keys configured
**Discovered:** 2026-09-06
**Impact:** Stripe service returns mock data
**Fix:** Add `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` to `.env`

### 🟢 #12 — No LLM keys configured
**Discovered:** 2026-09-06
**Impact:** Ella interview engine falls back to canned responses
**Fix:** Add `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to `.env`

---

## Testing Gaps

### 🟢 #13 — No E2E test for full show flow
**Discovered:** 2026-09-06
**Impact:** Cannot verify Episode Zero works end-to-end
**Fix:** Create Playwright tests for: create → submit → draw → start → perform → interview → end

### 🟢 #14 — No WebSocket integration tests
**Discovered:** 2026-09-06
**Impact:** Cannot test live show coordination
**Fix:** Add WebSocket client tests for stage and audience connections

### 🟢 #15 — No draw verification test with known seed
**Discovered:** 2026-09-06
**Impact:** Cannot verify deterministic draw is truly deterministic across runs
**Fix:** Create test fixture with fixed seed and expected output

### 🟡 #19 — test_list_comedians event loop mismatch
**Discovered:** 2026-09-06
**Impact:** asyncpg connection pool gets connections from wrong event loop when db.refresh triggers lazy loads
**Fix:** Add conftest.py with proper async session fixture bound to test event loop
**Note:** Pre-existing issue, previously hidden because test skipped without DB

---

## Security Concerns

### 🟢 #16 — CORS allows all origins in development
**Discovered:** 2026-09-06
**Impact:** Any website can make API requests
**Fix:** Restrict to `freak.town` and `localhost:5173` in production

### 🟢 #17 — No rate limiting on public endpoints
**Discovered:** 2026-09-06
**Impact:** DDoS possible on unauthenticated endpoints
**Fix:** Add rate limiting middleware

### 🟢 #18 — API key hashing uses SHA-256 without salt
**Discovered:** 2026-09-06
**Impact:** If DB is compromised, keys can be rainbow-tabled
**Fix:** Add per-key salt or use bcrypt

---

## Peer Review Fixes (2026-09-06)

### ✅ P0 — Python routes don't match canonical domain model
**Fixed:** Comedian now requires owner_user_id from auth, ActVersion uses revision/manifest/content_sha256 with full 64-char hash, Submission → draw → Appearance flow implemented

### ✅ P0 — Authentication not safe
**Fixed:** Added require_admin_from_api_key, scope checking actually enforced

### ✅ P0 — Payments unverified
**Fixed:** Added warning comments, confirmed_tip now requires verified provider state

### ✅ P1 — get_next_seq race condition
**Fixed:** Uses PostgreSQL advisory locks for concurrency safety

### ✅ P1 — check_scope always returns True
**Fixed:** Now actually checks scopes from API key

### ✅ P1 — Rate limiter datetime bug
**Fixed:** Changed from datetime.replace(timestamp=...) to timedelta subtraction

### ✅ P1 — Performance compiler bugs
**Fixed:** Question detection now checks ? before stripping punctuation

### ✅ P1 — External agent SSRF risk
**Fixed:** Feature flagged OFF by default, added URL validation with private IP blocking

### ✅ P0 — Migration describes older application
**Fixed:** Rewrote 001_initial_schema.py with canonical domain model (users, submissions, appearances)

### ✅ P0 — Cloudflare runtime not buildable
**Fixed:** Added package.json, tsconfig.json, fixed Worker imports

### ✅ P0 — EpisodeRoom not durable or access-controlled
**Fixed:** Hydrates state from storage, validates WebSocket credentials, persists events before broadcasting, session-based crowd dedup

---

## Resolved Issues

### ✅ #19 — Broken imports in backend/main.py
**Discovered:** 2026-09-06
**Fixed:** 2026-09-06
**Solution:** Moved models.py to models/__init__.py, fixed stage.py router

### ✅ #20 — EpisodeContestant doing too many jobs
**Discovered:** 2026-09-06
**Fixed:** 2026-09-06
**Solution:** Split into Submission (joins pool) and Appearance (selected into show)

### ✅ #21 — ActVersion hash was truncated
**Discovered:** 2026-09-06
**Fixed:** 2026-09-06
**Solution:** Now uses full SHA-256 of canonical manifest JSON

### ✅ #22 — Event seq hardcoded to 0 and 1
**Discovered:** 2026-09-06
**Fixed:** 2026-09-06
**Solution:** Created `emit_event()` helper with auto-assigned seq

### ✅ #23 — SQLite in .env.example
**Discovered:** 2026-09-06
**Fixed:** 2026-09-06
**Solution:** Changed to PostgreSQL async URL

---

## Build Stats

| Metric | Value |
|--------|-------|
| Python files | 28 |
| Python lines | 4,537 |
| TypeScript files | 4 |
| Domain models | 14 |
| API endpoints | 25+ |
| MCP tools | 11 |
| Unit tests | 18 (all passing) |
| Integration tests | 11 (10 passing, 1 event loop infra issue) |
| Services | 12 |
| Seed comedians | 5 |
| DB tables | 16 |
| DB enums | 9 |

---

## Migration Fixes (2026-09-06)

### ✅ Migration enum creation bug
**Fixed:** SQLAlchemy `sa.Enum(..., create_type=False)` doesn't prevent `_on_table_create` from re-creating the type. Changed migration to create enums via raw SQL `DO $$ BEGIN ... EXCEPTION WHEN duplicate_object THEN null; END $$` and use `sa.String` columns in `create_table`.

### ✅ ORM enum type mismatch
**Fixed:** ORM models used `Enum(UserRole)` etc. as column types, generating `CAST($1 AS episodestatus)` against VARCHAR columns. Changed all enum columns in ORM to `String(N)` while keeping Python enum classes for validation.

### ✅ Alembic async engine enum conflict
**Fixed:** `alembic/env.py` now detects sync PostgreSQL URLs and uses sync engine for migrations, avoiding asyncpg enum creation issues.

### ✅ .env.example stale credentials
**Fixed:** Updated from `killella:killella` to `freak_town:freak_town` to match docker-compose.
