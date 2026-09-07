/**
 * API routes for the Freak Town Worker.
 */

import { Hono } from 'hono';
import { authMiddleware, requireAdmin, type AppBindings } from '../auth/middleware';

const app = new Hono<AppBindings>();

// ── Public Routes ─────────────────────────────────────────────────────

app.get('/episodes/live', async (c) => {
  const db = c.env.DB;
  const result = await db.prepare(
    "SELECT id, title, status, current_phase FROM episodes WHERE status IN ('live', 'ready', 'open') ORDER BY created_at DESC LIMIT 1"
  ).first();

  return c.json({ episode: result || null });
});

app.get('/episodes/:id', async (c) => {
  const db = c.env.DB;
  const id = c.req.param('id');

  const episode = await db.prepare("SELECT * FROM episodes WHERE id = ?").bind(id).first();
  if (!episode) return c.json({ error: 'Not found' }, 404);

  const submissions = await db.prepare(
    "SELECT COUNT(*) as count FROM submissions WHERE episode_id = ?"
  ).bind(id).first();

  return c.json({ ...episode, submission_count: submissions?.count || 0 });
});

app.get('/comedians/:slug', async (c) => {
  const db = c.env.DB;
  const slug = c.req.param('slug');

  const comedian = await db.prepare("SELECT * FROM comedians WHERE slug = ?").bind(slug).first();
  if (!comedian) return c.json({ error: 'Not found' }, 404);

  const versions = await db.prepare(
    "SELECT id, revision, created_at FROM act_versions WHERE comedian_id = ? ORDER BY revision DESC"
  ).bind(comedian.id).all();

  return c.json({ ...comedian, versions: versions.results });
});

// ── Authenticated Routes ──────────────────────────────────────────────

app.use('/comedians', authMiddleware);
app.use('/comedians/*', authMiddleware);
app.use('/submissions', authMiddleware);
app.use('/submissions/*', authMiddleware);

app.post('/comedians', async (c) => {
  const user = c.get('user');
  const body = await c.req.json();
  const db = c.env.DB;

  // Create comedian
  const id = crypto.randomUUID();
  const slug = body.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  await db.prepare(
    "INSERT INTO comedians (id, owner_user_id, name, slug, premise, body_archetype) VALUES (?, ?, ?, ?, ?, ?)"
  ).bind(id, user.id, body.name, slug, body.premise, body.body_archetype).run();

  // Create first act version
  const actId = crypto.randomUUID();
  const manifest = {
    schemaVersion: 1,
    character: { name: body.name, deal: body.character_deal, facts: body.character_facts || [] },
    body: { family: body.body_archetype, variant: null, outfit: null },
    voice: { voiceId: body.voice_profile || 'default' },
    minute: { text: body.minute_text, authorship: body.minute_authorship || 'ai', assistance: [] },
    interview: { controller: body.interview_controller || 'freak_town_ai', facts: body.character_facts || [] },
  };

  const contentHash = await hashManifest(manifest);

  await db.prepare(
    "INSERT INTO act_versions (id, comedian_id, revision, created_by_user_id, manifest, content_sha256, sealed_at) VALUES (?, ?, 1, ?, ?, ?, datetime('now'))"
  ).bind(actId, id, user.id, JSON.stringify(manifest), contentHash).run();

  return c.json({ comedian_id: id, act_version_id: actId, slug, status: 'created' }, 201);
});

app.post('/submissions', async (c) => {
  const user = c.get('user');
  const body = await c.req.json();
  const db = c.env.DB;

  // Verify episode is open
  const episode = await db.prepare("SELECT * FROM episodes WHERE id = ?").bind(body.episode_id).first();
  if (!episode || episode.status !== 'open') {
    return c.json({ error: 'Episode not open' }, 400);
  }

  // Verify comedian ownership
  const comedian = await db.prepare("SELECT * FROM comedians WHERE id = ? AND owner_user_id = ?").bind(body.comedian_id, user.id).first();
  if (!comedian) return c.json({ error: 'Not your comedian' }, 403);

  // Get act version
  let actVersionId = body.act_version_id;
  if (!actVersionId) {
    const av = await db.prepare(
      "SELECT id FROM act_versions WHERE comedian_id = ? ORDER BY revision DESC LIMIT 1"
    ).bind(body.comedian_id).first();
    actVersionId = av?.id;
  }

  if (!actVersionId) return c.json({ error: 'No act version found' }, 400);

  // Create submission
  const id = crypto.randomUUID();
  await db.prepare(
    "INSERT INTO submissions (id, episode_id, comedian_id, act_version_id, submitted_by_user_id, qualification_status) VALUES (?, ?, ?, ?, ?, 'submitted')"
  ).bind(id, body.episode_id, body.comedian_id, actVersionId, user.id).run();

  return c.json({ submission_id: id, status: 'submitted' }, 201);
});

// ── Admin Routes ──────────────────────────────────────────────────────

app.use('/admin/*', authMiddleware);
app.use('/admin/*', requireAdmin);

app.post('/admin/episodes', async (c) => {
  const body = await c.req.json();
  const db = c.env.DB;

  const id = crypto.randomUUID();
  await db.prepare(
    "INSERT INTO episodes (id, title, status, current_phase, max_appearances) VALUES (?, ?, 'open', 'pre_show', ?)"
  ).bind(id, body.title, body.max_appearances || 5).run();

  return c.json({ episode_id: id, status: 'created' }, 201);
});

// ── Helpers ───────────────────────────────────────────────────────────

async function hashManifest(manifest: object): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(JSON.stringify(manifest, Object.keys(manifest).sort()));
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

export { app as apiRouter };
