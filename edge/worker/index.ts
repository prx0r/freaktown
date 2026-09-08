/**
 * Freak Town — Cloudflare Worker entry point.
 *
 * This is the live nervous system.
 * The Python backend handles offline research/evaluation.
 * This Worker handles the real-time show runtime.
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
// NOTE (migration): the D1-backed business api/ (episodes/comedians reads)
// was deliberately NOT ported — Postgres is canonical business truth (§17).
// Edge reads return after Hyperdrive provisioning; the DO is unaffected.
import { authMiddleware, requireAdmin, type AppBindings } from './auth/middleware';
import { EpisodeRoom } from './episode-room';

export { EpisodeRoom };

export type Env = {
  DB: D1Database;
  R2: R2Bucket;
  EPISODE_ROOM: DurableObjectNamespace;
  PRIVY_APP_ID: string;
  PRIVY_APP_SECRET: string;
  OPENAI_API_KEY: string;
  ANTHROPIC_API_KEY: string;
  ELEVENLABS_API_KEY: string;
  STAGE_TOKEN_SECRET: string;
  ASSETS: { fetch: typeof fetch };
};

const app = new Hono<AppBindings>();

// ── Middleware ─────────────────────────────────────────────────────────

app.use('*', cors({
  origin: ['http://localhost:5173', 'https://freak.town'],
  allowMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowHeaders: ['Content-Type', 'Authorization', 'X-API-Key'],
}));

// ── Health ────────────────────────────────────────────────────────────

app.get('/health', (c) => {
  return c.json({ status: 'ok', service: 'freak-town', runtime: 'cloudflare-worker' });
});

// ── API Routes ────────────────────────────────────────────────────────
// Business reads live behind FastAPI/Postgres; edge api/ returns with Hyperdrive.

// ── Live Room (EpisodeRoom Durable Object) ────────────────────────────
// One DO instance per episode. This is the canonical LIVE runtime.

function getRoom(c: { env: Env }, episodeId: string) {
  return c.env.EPISODE_ROOM.getByName(episodeId);
}

app.get('/live/:episodeId/ws', async (c) => {
  const episodeId = c.req.param('episodeId');
  if (!episodeId) return c.json({ error: 'episodeId required' }, 400);
  const stub = getRoom(c, episodeId);
  const url = new URL(c.req.url);
  // Forward query params (type, token, sessionId, since) to the DO,
  // plus the episodeId the DO instance is authoritative for.
  const params = new URLSearchParams(url.search);
  params.set('episodeId', episodeId);
  return stub.fetch(`https://episode-room/ws?${params.toString()}`);
});

app.get('/live/:episodeId/state', async (c) => {
  const episodeId = c.req.param('episodeId');
  if (!episodeId) return c.json({ error: 'episodeId required' }, 400);
  const stub = getRoom(c, episodeId);
  return stub.fetch('https://episode-room/state');
});

app.get('/live/:episodeId/sense', async (c) => {
  const episodeId = c.req.param('episodeId');
  if (!episodeId) return c.json({ error: 'episodeId required' }, 400);
  const stub = getRoom(c, episodeId);
  return stub.fetch('https://episode-room/sense');
});

app.post('/live/:episodeId/command', authMiddleware, requireAdmin, async (c) => {
  const episodeId = c.req.param('episodeId');
  if (!episodeId) return c.json({ error: 'episodeId required' }, 400);
  const stub = getRoom(c, episodeId);
  const incoming = (await c.req.json()) as Record<string, unknown>;
  return stub.fetch('https://episode-room/command', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...incoming, episodeId }),
  });
});

app.post('/live/:episodeId/stage-token', authMiddleware, requireAdmin, async (c) => {
  const episodeId = c.req.param('episodeId');
  if (!episodeId) return c.json({ error: 'episodeId required' }, 400);
  const stub = getRoom(c, episodeId);
  const incoming = (await c.req.json().catch(() => ({}))) as Record<string, unknown>;
  return stub.fetch('https://episode-room/stage-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...incoming, episodeId }),
  });
});

// ── Static Assets ─────────────────────────────────────────────────────

app.get('*', async (c) => {
  return c.env.ASSETS.fetch(c.req.raw);
});

export default app;
