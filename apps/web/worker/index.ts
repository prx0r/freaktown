/**
 * Freak Town — Cloudflare Worker entry point.
 *
 * This is the live nervous system.
 * The Python backend handles offline research/evaluation.
 * This Worker handles the real-time show runtime.
 */

import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { apiRouter } from './api/index';
import { authMiddleware } from './auth/middleware';

export type Env = {
  DB: D1Database;
  R2: R2Bucket;
  TTS_QUEUE: Queue;
  AI_QUEUE: Queue;
  KV: KVNamespace;
  PRIVY_APP_ID: string;
  PRIVY_APP_SECRET: string;
  OPENAI_API_KEY: string;
  ANTHROPIC_API_KEY: string;
  ELEVENLABS_API_KEY: string;
  ASSETS: { fetch: typeof fetch };
};

const app = new Hono<{ Bindings: Env }>();

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

app.route('/v1', apiRouter);

// ── Static Assets ─────────────────────────────────────────────────────

app.get('*', async (c) => {
  return c.env.ASSETS.fetch(c.req.raw);
});

export default app;
