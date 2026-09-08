/**
 * EpisodeRoom Durable Object — canonical LIVE runtime for one episode.
 *
 * One instance per episode (`getByName(episodeId)`).
 *
 * Invariants:
 * - Persist BEFORE broadcast (every event hits storage first).
 * - No in-memory Maps as authority. Connection state lives in
 *   WebSocket attachments + tags (`ctx.getWebSockets(tag)`), which
 *   survive hibernation. Live state lives in DO storage, hydrated
 *   in the constructor.
 * - Stage/puppeteer connections require HMAC-signed tokens.
 * - Events are stored under zero-padded keys (`event:000000000042`)
 *   so the stage can reconnect at seq N and replay from N+1.
 */

import { DurableObject } from 'cloudflare:workers';

import { CameraCutPayloadV1, type EllaSenseV1 } from '../src/contracts/show';

export type EpisodeState = {
  episodeId: string;
  phase: string;
  activeAppearanceId: string | null;
  seq: number;
  startedAt: string | null;
  isPaused: boolean;
};

type Role = 'stage' | 'audience' | 'puppeteer';

type ClientAttachment = {
  role: Role;
  sessionId: string;
  appearanceId?: string;
  authenticated: boolean;
  connectedAt: number;
};

type StageTokenPayload = {
  ep: string;
  role: 'stage' | 'puppeteer';
  exp: number; // unix seconds
};

type CrowdWindow = {
  laughs: number;
  claps: number;
  boos: number;
  crickets: number;
  groans: number;
  uniqueSessions: string[];
  startTime: number;
};

/** Explicit reaction vocabulary. Anything else is discarded at the door. */
const SUPPORTED_REACTIONS: ReadonlySet<string> = new Set([
  'laugh', 'clap', 'boo', 'crickets', 'groan', 'love', 'wtf',
]);

const ALARM_INTERVAL_MS = 5000;
const SEQ_PAD = 12;

// ── base64url helpers ────────────────────────────────────────────────

function b64urlEncode(data: Uint8Array | string): string {
  const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : data;
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function b64urlDecode(s: string): Uint8Array {
  const b64 = s.replace(/-/g, '+').replace(/_/g, '/');
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

// ── EpisodeRoom ──────────────────────────────────────────────────────

export class EpisodeRoom extends DurableObject {
  private episodeState: EpisodeState = {
    episodeId: '',
    phase: 'pre_show',
    activeAppearanceId: null,
    seq: 0,
    startedAt: null,
    isPaused: false,
  };

  // Best-effort in-memory crowd windows. Persisted every ALARM_INTERVAL_MS
  // and rehydrated in the constructor, so at most one window is lost on
  // eviction. Raw per-event data is the client's responsibility to resend
  // after reconnect (reactions are idempotent by session+clientSeq window).
  private crowdWindows: Map<string, CrowdWindow> = new Map();
  private lastReactionAt: Map<string, number> = new Map();

  constructor(state: DurableObjectState, env: any) {
    super(state, env);

    this.ctx.blockConcurrencyWhile(async () => {
      const saved = await this.ctx.storage.get<EpisodeState>('episodeState');
      if (saved) {
        this.episodeState = saved;
      }

      // Rehydrate crowd windows persisted by the alarm handler.
      // Normalize older shapes (pre-crickets/groans) defensively.
      const crowd = await this.ctx.storage.list<CrowdWindow>({ prefix: 'crowd:' });
      for (const [key, window] of crowd) {
        const appearanceId = key.slice('crowd:'.length);
        this.crowdWindows.set(appearanceId, {
          laughs: window.laughs ?? 0,
          claps: window.claps ?? 0,
          boos: window.boos ?? 0,
          crickets: window.crickets ?? 0,
          groans: window.groans ?? 0,
          uniqueSessions: window.uniqueSessions ?? [],
          startTime: window.startTime ?? Date.now(),
        });
      }

      // If a show was mid-flight when we were evicted, resume persistence
      if (saved && saved.phase !== 'pre_show' && saved.phase !== 'ended') {
        await this.ensureAlarm();
      }
    });
  }

  // ── HTTP entry points ──────────────────────────────────────────────

  /** Bind this instance to an episode on first contact. Persists. */
  private async bindEpisode(episodeId: string) {
    if (!episodeId) return;
    if (!this.episodeState.episodeId) {
      this.episodeState.episodeId = episodeId;
      await this.ctx.storage.put('episodeState', this.episodeState);
    }
  }

  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/ws') {
      const episodeId = url.searchParams.get('episodeId') || '';
      await this.bindEpisode(episodeId);
      return this.handleWebSocketUpgrade(request);
    }

    if (url.pathname === '/state') {
      return Response.json({
        ...this.episodeState,
        connections: {
          stage: this.ctx.getWebSockets('role:stage').length,
          audience: this.ctx.getWebSockets('role:audience').length,
          puppeteer: this.ctx.getWebSockets('role:puppeteer').length,
        },
      });
    }

    if (url.pathname === '/sense') {
      return Response.json(await this.getSense());
    }

    if (url.pathname === '/command' && request.method === 'POST') {
      return this.handleCommand(request);
    }

    if (url.pathname === '/stage-token' && request.method === 'POST') {
      return this.handleMintToken(request);
    }

    return Response.json({ error: 'Not found' }, { status: 404 });
  }

  // ── Stage tokens (HMAC-signed) ─────────────────────────────────────

  private get secret(): string {
    return (this.env as any).STAGE_TOKEN_SECRET ?? '';
  }

  private async signToken(payload: StageTokenPayload): Promise<string> {
    const body = b64urlEncode(JSON.stringify(payload));
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(this.secret),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['sign']
    );
    const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(body));
    return `${body}.${b64urlEncode(new Uint8Array(sig))}`;
  }

  private async verifyToken(
    token: string,
    episodeId: string,
    role: 'stage' | 'puppeteer'
  ): Promise<boolean> {
    try {
      if (!this.secret) return false; // fail closed: no secret, no access
      const [body, sig] = token.split('.');
      if (!body || !sig) return false;

      const key = await crypto.subtle.importKey(
        'raw',
        new TextEncoder().encode(this.secret),
        { name: 'HMAC', hash: 'SHA-256' },
        false,
        ['verify']
      );
      const ok = await crypto.subtle.verify(
        'HMAC',
        key,
        b64urlDecode(sig),
        new TextEncoder().encode(body)
      );
      if (!ok) return false;

      const payload = JSON.parse(new TextDecoder().decode(b64urlDecode(body))) as StageTokenPayload;
      if (payload.ep !== episodeId) return false;
      if (payload.role !== role) return false;
      if (payload.exp * 1000 < Date.now()) return false;
      return true;
    } catch {
      return false;
    }
  }

  private async handleMintToken(request: Request): Promise<Response> {
    // Called by the Worker route, which already enforces admin auth.
    const body = (await request.json()) as { episodeId?: string; role?: 'stage' | 'puppeteer'; ttlSec?: number };
    if (!body.episodeId || (body.role !== 'stage' && body.role !== 'puppeteer')) {
      return Response.json({ error: 'episodeId and role (stage|puppeteer) required' }, { status: 400 });
    }
    await this.bindEpisode(body.episodeId);
    if (!this.secret) {
      return Response.json({ error: 'STAGE_TOKEN_SECRET not configured' }, { status: 500 });
    }
    const ttlSec = Math.min(body.ttlSec ?? 4 * 3600, 24 * 3600);
    const token = await this.signToken({
      ep: body.episodeId,
      role: body.role,
      exp: Math.floor(Date.now() / 1000) + ttlSec,
    });
    return Response.json({ token, expiresInSec: ttlSec });
  }

  // ── WebSocket upgrade ──────────────────────────────────────────────

  private handleWebSocketUpgrade(request: Request): Response {
    const url = new URL(request.url);
    const role = (url.searchParams.get('type') || 'audience') as Role;
    const token = url.searchParams.get('token') ?? '';
    const sessionId = url.searchParams.get('sessionId') || crypto.randomUUID();
    const appearanceId = url.searchParams.get('appearanceId') || undefined;
    const since = parseInt(url.searchParams.get('since') || '0', 10) || 0;

    if (role !== 'stage' && role !== 'audience' && role !== 'puppeteer') {
      return new Response('Invalid client type', { status: 400 });
    }

    const pair = new WebSocketPair();
    const [client, server] = [pair[0], pair[1]];

    // Tags are the queryable source of truth for connection sets.
    this.ctx.acceptWebSocket(server, [`role:${role}`, `session:${sessionId}`]);

    // Attachment survives hibernation; validated lazily per message so a
    // token expiring mid-show does not kill an already-admitted socket, but
    // privileged actions re-verify the attachment flag.
    const attachment: ClientAttachment = {
      role,
      sessionId,
      appearanceId,
      authenticated: false, // resolved async below for privileged roles
      connectedAt: Date.now(),
    };
    server.serializeAttachment(attachment);

    // Resolve auth asynchronously; privileged handlers check the flag.
    if (role === 'stage' || role === 'puppeteer') {
      const episodeId = this.episodeState.episodeId || url.searchParams.get('episodeId') || '';
      void this.verifyToken(token, episodeId, role).then((ok) => {
        try {
          const current = server.deserializeAttachment() as ClientAttachment | null;
          if (current) {
            current.authenticated = ok;
            server.serializeAttachment(current);
          }
          if (!ok) {
            server.send(JSON.stringify({ type: 'auth.rejected', data: { reason: 'invalid token' } }));
            server.close(4401, 'Unauthorized');
          }
        } catch {
          // Socket already gone; nothing to do.
        }
      });
    } else {
      attachment.authenticated = true;
      try {
        server.serializeAttachment(attachment);
      } catch {
        // Socket already gone; nothing to do.
      }
    }

    // Minimal hello; the client sends `ready` with last_seq and gets
    // snapshot + replay of events since that seq.
    try {
      server.send(JSON.stringify({ type: 'hello', data: { sessionId, since } }));
    } catch {
      // Socket already gone; nothing to do.
    }

    return new Response(null, { status: 101, webSocket: client });
  }

  // ── WebSocket messages ─────────────────────────────────────────────

  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer) {
    try {
      const data = JSON.parse(message as string) as { type?: string; [k: string]: unknown };
      const attachment = ws.deserializeAttachment() as ClientAttachment | null;
      if (!attachment) return;

      switch (data.type) {
        case 'ready':
          await this.handleReady(ws, attachment, Number(data.last_seq ?? 0) || 0);
          break;
        case 'reaction':
          if (attachment.role === 'audience') {
            await this.handleReaction(data, attachment);
          }
          break;
        case 'tip':
          if (attachment.role === 'audience') {
            await this.handleTip(data, attachment);
          }
          break;
        case 'dialogue':
          if (attachment.role === 'puppeteer' && attachment.authenticated) {
            await this.handlePuppeteerDialogue(data, attachment);
          }
          break;
        case 'camera.cut':
          if ((attachment.role === 'stage' || attachment.role === 'puppeteer') && attachment.authenticated) {
            // Shared contract gates the payload: unknown camera names are
            // dropped here, never persisted, never broadcast.
            const parsed = CameraCutPayloadV1.safeParse({
              camera: data.camera,
              performance_id: this.episodeState.activeAppearanceId,
              set_time_ms: data.set_time_ms ?? null,
              source: 'human_director',
            });
            if (!parsed.success) break;
            await this.executeCommand('camera.cut', {
              actor: attachment.role,
              ...parsed.data,
            });
          }
          break;
        case 'stage.ack':
          // Readiness/completion ACKs from the stage's own authenticated
          // socket (e.g. performance.ready after preload). Persisted like
          // any command so replay reconstructs the same show.
          if (attachment.role === 'stage' && attachment.authenticated) {
            const ackEvent = data.event;
            if (typeof ackEvent === 'string' && ackEvent) {
              const payload: Record<string, unknown> = { actor: 'stage' };
              for (const [k, v] of Object.entries(data)) {
                if (k !== 'type' && k !== 'event') payload[k] = v;
              }
              await this.executeCommand(ackEvent, payload);
            }
          }
          break;
        case 'heartbeat':
          ws.send(JSON.stringify({ type: 'heartbeat.ack' }));
          break;
        default:
          break;
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  }

  async webSocketClose(_ws: WebSocket) {
    // No bookkeeping needed: connection sets are derived from
    // ctx.getWebSockets(tag), which the runtime maintains.
  }

  async webSocketError(_ws: WebSocket, error: unknown) {
    console.error('WebSocket error:', error);
  }

  // ── Snapshot + replay ──────────────────────────────────────────────

  private eventKey(seq: number): string {
    return `event:${String(seq).padStart(SEQ_PAD, '0')}`;
  }

  private async handleReady(ws: WebSocket, attachment: ClientAttachment, lastSeq: number) {
    // Full snapshot first
    ws.send(
      JSON.stringify({
        type: 'show.snapshot',
        data: {
          episode_id: this.episodeState.episodeId,
          phase: this.episodeState.phase,
          active_appearance_id: this.episodeState.activeAppearanceId,
          seq: this.episodeState.seq,
          is_paused: this.episodeState.isPaused,
        },
      })
    );

    // Replay every event after lastSeq, in order. Zero-padded keys sort
    // lexicographically in seq order.
    const stored = await this.ctx.storage.list<Record<string, unknown>>({ prefix: 'event:' });
    const replay = [...stored.values()]
      .filter((e) => typeof (e as { seq?: unknown }).seq === 'number' && ((e as { seq: number }).seq as number) > lastSeq)
      .sort((a, b) => ((a as { seq: number }).seq as number) - ((b as { seq: number }).seq as number));

    for (const event of replay) {
      try {
        ws.send(JSON.stringify({ type: 'show.event', data: event }));
      } catch {
        break; // socket died mid-replay
      }
    }

    void attachment;
  }

  // ── EllaSense (compact live context) ─────────────────────────────
  //
  // Normalized perception for Ella, not the raw firehose: crowd state,
  // phase, pot total. Ella polls at ~1Hz. set_time_ms is null — only the
  // stage knows the media playhead; the server never invents one.

  async getSense(): Promise<EllaSenseV1> {
    const windowKey = this.episodeState.activeAppearanceId || 'none';
    const window = this.crowdWindows.get(windowKey);

    let potCents = 0;
    const stored = await this.ctx.storage.list<{ type?: unknown; payload?: unknown }>({
      prefix: 'event:',
    });
    for (const e of stored.values()) {
      if (e?.type !== 'pot.contribution') continue;
      const payload = (e.payload ?? {}) as Record<string, unknown>;
      if (typeof payload.amount_cents === 'number' && payload.amount_cents > 0) {
        potCents += Math.floor(payload.amount_cents);
      }
    }

    return {
      episode_id: this.episodeState.episodeId,
      phase: this.episodeState.phase,
      active_appearance_id: this.episodeState.activeAppearanceId,
      seq: this.episodeState.seq,
      is_paused: this.episodeState.isPaused,
      set_time_ms: null,
      crowd: {
        laugh_events: window?.laughs ?? 0,
        claps: window?.claps ?? 0,
        boos: window?.boos ?? 0,
        crickets: window?.crickets ?? 0,
        groans: window?.groans ?? 0,
        unique_laughers: window?.uniqueSessions.length ?? 0,
      },
      pot_cents: potCents,
      updated_at: new Date().toISOString(),
    };
  }

  // ── Commands (persist before broadcast) ────────────────────────────

  private async handleCommand(request: Request): Promise<Response> {
    const body = (await request.json()) as { commandId?: string; type?: string; payload?: Record<string, unknown>; episodeId?: string };
    const { commandId, type, payload } = body;

    if (!type) {
      return Response.json({ error: 'type required' }, { status: 400 });
    }

    if (body.episodeId) {
      await this.bindEpisode(body.episodeId);
    }

    // Idempotency check
    if (commandId) {
      const existing = await this.ctx.storage.get<number>(`cmd:${commandId}`);
      if (existing !== undefined) {
        return Response.json({ status: 'already_executed', seq: existing });
      }
    }

    const event = await this.executeCommand(type, payload ?? {});

    if (commandId && event) {
      await this.ctx.storage.put(`cmd:${commandId}`, event.seq);
    }

    return Response.json({ status: 'ok', event });
  }

  private async executeCommand(type: string, payload: Record<string, unknown>) {
    this.episodeState.seq += 1;
    const seq = this.episodeState.seq;

    const event = {
      seq,
      type,
      actor: (payload.actor as string) || 'system',
      payload,
      created_at: new Date().toISOString(),
    };

    // Persist event BEFORE broadcasting
    await this.ctx.storage.put(this.eventKey(seq), event);

    // Update live state
    switch (type) {
      case 'show.start':
        this.episodeState.phase = 'intro';
        this.episodeState.startedAt = new Date().toISOString();
        break;
      case 'show.phase':
      case 'phase.change':
        if (typeof payload.phase === 'string') this.episodeState.phase = payload.phase;
        break;
      case 'character.enter':
        if (typeof payload.appearanceId === 'string') {
          this.episodeState.activeAppearanceId = payload.appearanceId;
        }
        break;
      case 'character.exit':
        this.episodeState.activeAppearanceId = null;
        break;
      case 'show.pause':
        this.episodeState.isPaused = true;
        break;
      case 'show.resume':
        this.episodeState.isPaused = false;
        break;
      case 'show.end':
        this.episodeState.phase = 'ended';
        break;
      default:
        break;
    }

    // Persist updated state
    await this.ctx.storage.put('episodeState', this.episodeState);

    // Keep periodic persistence alive from the first command onward
    await this.ensureAlarm();

    // Broadcast to all connected clients
    this.broadcast(JSON.stringify({ type: 'show.event', data: event }));

    return event;
  }

  // ── Audience reactions (raw ML events + derived aggregates) ──────
  //
  // Raw reactions are more valuable than aggregates: every accepted
  // reaction is persisted with session_id + client_seq + performance_id
  // + set_time_ms + source, and the 1s crowd buckets are DERIVED from
  // the raw log (reproducible both directions). Aggregates alone would
  // throw away the dataset the whole system is designed to produce.

  private async handleReaction(data: { [k: string]: unknown }, attachment: ClientAttachment) {
    const reaction = data.reaction as string;
    if (!SUPPORTED_REACTIONS.has(reaction)) return;

    // Reactions count only while a performer is on stage.
    if (!this.episodeState.activeAppearanceId || this.episodeState.isPaused) return;

    // Duplicate/out-of-order client_seq from the same session is a
    // resend: ignore. The high-water mark lives in storage (not memory)
    // so dedup survives hibernation/eviction exactly like the raw log.
    const clientSeq = Number(data.client_seq ?? NaN);
    if (!Number.isInteger(clientSeq) || clientSeq <= 0) return;
    const highKey = `sess:${attachment.sessionId}`;
    const high = (await this.ctx.storage.get<number>(highKey)) ?? 0;
    if (clientSeq <= high) return;

    // Best-effort per-session rate limit: max 1 reaction / 250ms
    const now = Date.now();
    const last = this.lastReactionAt.get(attachment.sessionId) ?? 0;
    if (now - last < 250) return;
    this.lastReactionAt.set(attachment.sessionId, now);

    const setTimeMs = Number(data.set_time_ms ?? 0) || 0;
    const source = typeof data.source === 'string' ? data.source : 'freaktown_web';

    // 1. Persist the raw event first.
    this.episodeState.seq += 1;
    const seq = this.episodeState.seq;
    const rawEvent = {
      seq,
      event_id: crypto.randomUUID(),
      episode_id: this.episodeState.episodeId,
      performance_id: this.episodeState.activeAppearanceId,
      session_id: attachment.sessionId,
      client_seq: clientSeq,
      type: 'reaction',
      reaction,
      set_time_ms: setTimeMs,
      server_received_at: new Date(now).toISOString(),
      source,
    };
    await this.ctx.storage.put(this.eventKey(seq), rawEvent);
    await this.ctx.storage.put(highKey, clientSeq);
    await this.ctx.storage.put('episodeState', this.episodeState);
    await this.ensureAlarm();

    // 2. Derive the live aggregate.
    const windowKey = this.episodeState.activeAppearanceId || 'none';
    let window = this.crowdWindows.get(windowKey);
    if (!window) {
      window = { laughs: 0, claps: 0, boos: 0, crickets: 0, groans: 0, uniqueSessions: [], startTime: now };
      this.crowdWindows.set(windowKey, window);
    }

    if (reaction === 'laugh') {
      window.laughs += 1;
      // Session-based dedup: one session = one unique laugher per window
      if (!window.uniqueSessions.includes(attachment.sessionId)) {
        window.uniqueSessions.push(attachment.sessionId);
      }
    } else if (reaction === 'clap') {
      window.claps += 1;
    } else if (reaction === 'boo') {
      window.boos += 1;
    } else if (reaction === 'crickets') {
      window.crickets += 1;
    } else if (reaction === 'groan') {
      window.groans += 1;
    } else {
      // love / wtf: counted as engagement volume only
      window.laughs += 0;
    }

    this.broadcastToRole(
      'audience',
      JSON.stringify({
        type: 'crowd.update',
        // snake_case wire names matching the frontend CrowdState
        // (freaktown.event.v1) — never camelCase on the wire.
        data: {
          laugh_events: window.laughs,
          claps: window.claps,
          boos: window.boos,
          crickets: window.crickets ?? 0,
          groans: window.groans ?? 0,
          unique_laughers: window.uniqueSessions.length,
        },
      })
    );
  }

  // ── Tips (display + ML record) ─────────────────────────────────────
  //
  // NOTE: this records the tip as a persisted show event (content + ML).
  // Actual payment capture (card/Apple Pay/wallet rails) happens in the
  // FastAPI control plane, which emits the authoritative receipt. The DO
  // event is the on-stage display record: amount + message + timing.

  private async handleTip(data: { [k: string]: unknown }, attachment: ClientAttachment) {
    const amount_cents = data.amount_cents;
    if (typeof amount_cents !== 'number' || !Number.isInteger(amount_cents)) return;
    if (amount_cents <= 0 || amount_cents > 50_000) return; // $0 < tip <= $500

    const rawMessage = typeof data.message === 'string' ? data.message : '';
    const message = rawMessage.slice(0, 140); // on-stage chyron length

    const appearanceId =
      typeof data.appearance_id === 'string'
        ? data.appearance_id
        : this.episodeState.activeAppearanceId;

    await this.executeCommand('tip.received', {
      actor: `audience:${attachment.sessionId}`,
      appearanceId,
      amount_cents,
      message,
    });
  }

  // ── Puppeteer dialogue ─────────────────────────────────────────────

  private async handlePuppeteerDialogue(
    data: { [k: string]: unknown },
    attachment: ClientAttachment
  ) {
    const text = data.text as string;
    if (!text || typeof text !== 'string') return;

    // Only allow the puppeteer to control their assigned appearance,
    // and only while it is the active one.
    if (!attachment.appearanceId) return;
    if (this.episodeState.activeAppearanceId !== attachment.appearanceId) return;

    await this.executeCommand('stage.speak', {
      actor: `contestant_${attachment.appearanceId}`,
      appearanceId: attachment.appearanceId,
      text,
    });
  }

  // ── Broadcasts (tag-derived, hibernation-safe) ─────────────────────

  private broadcast(message: string) {
    for (const ws of this.ctx.getWebSockets()) {
      try {
        ws.send(message);
      } catch {
        // Dead socket; runtime prunes it.
      }
    }
  }

  private broadcastToRole(role: Role, message: string) {
    for (const ws of this.ctx.getWebSockets(`role:${role}`)) {
      try {
        ws.send(message);
      } catch {
        // Dead socket; runtime prunes it.
      }
    }
  }

  // ── Periodic persistence ───────────────────────────────────────────

  private async ensureAlarm() {
    const existing = await this.ctx.storage.getAlarm();
    if (existing == null) {
      await this.ctx.storage.setAlarm(Date.now() + ALARM_INTERVAL_MS);
    }
  }

  async alarm() {
    // Persist crowd windows so eviction loses at most one window
    for (const [appearanceId, window] of this.crowdWindows.entries()) {
      await this.ctx.storage.put(`crowd:${appearanceId}`, window);
    }
    this.crowdWindows.clear();
    this.lastReactionAt.clear();

    // Persist live state snapshot
    await this.ctx.storage.put('episodeState', this.episodeState);

    // Keep ticking while a show is live
    if (this.episodeState.phase !== 'ended') {
      await this.ctx.storage.setAlarm(Date.now() + ALARM_INTERVAL_MS);
    }
  }
}
