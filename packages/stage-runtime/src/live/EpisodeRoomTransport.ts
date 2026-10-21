/**
 * EpisodeRoomTransport — LiveTransport over the Cloudflare EpisodeRoom DO.
 *
 * - Socket: /live/:ep/ws?type=<role>&token=…&sessionId=…&since=…
 *   (stage needs the HMAC token minted by POST /live/:ep/stage-token).
 * - Commands: POST /live/:ep/command (admin key or Privy bearer).
 * - Reconnect: capped exponential backoff on surprise drops; explicit
 *   disconnect() never reconnects (StrictMode-safe, no zombies).
 * - Resume: reconnects send `since` = highest seq seen, the DO replays
 *   everything after it.
 */

import type { ShowEvent } from '@freaktown/contracts';
import {
  HandlerSet, newSessionId,
  type CommandResult, type LiveConnectOptions, type LiveHandlers, type LiveRole, type LiveTransport,
} from './LiveTransport';

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 15000;

export interface EpisodeRoomTransportOptions {
  /** Origin of the worker, e.g. "http://127.0.0.1:8787". Default: page origin. */
  baseUrl?: string;
  /** Admin API key (ft_…) or Privy JWT for commands. */
  authKey?: string;
  /** Path prefix in front of /live (e.g. "/perform" behind a proxy). */
  pathPrefix?: string;
}

function authHeaders(key?: string): Record<string, string> {
  if (!key) return {};
  if (key.startsWith('ft_')) return { 'X-API-Key': key };
  return { Authorization: `Bearer ${key}` };
}

export class EpisodeRoomTransport implements LiveTransport {
  readonly kind = 'episode-room' as const;
  private ws: WebSocket | null = null;
  private episodeId = '';
  private role: LiveRole = 'stage';
  private token?: string;
  private sessionId: string;
  private appearanceId?: string;
  private lastSeq = 0;
  private clientSeq = 0;
  private shouldReconnect = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;
  private handlers = new HandlerSet();
  private opts: EpisodeRoomTransportOptions;

  constructor(opts: EpisodeRoomTransportOptions = {}) {
    this.opts = opts;
    this.sessionId = newSessionId();
  }

  setAuthKey(key: string): void { this.opts.authKey = key; }

  subscribe(h: LiveHandlers): () => void { return this.handlers.add(h); }

  get connected(): boolean {
    return this.ws !== null && this.ws.readyState === 1;
  }

  private httpBase(): string {
    const origin = this.opts.baseUrl
      ?? (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : '');
    return `${origin.replace(/\/$/, '')}${this.opts.pathPrefix ?? ''}`;
  }

  private wsUrl(): string {
    const http = this.httpBase();
    const ws = http.startsWith('https:') ? http.replace(/^https:/, 'wss:') : http.replace(/^http:/, 'ws:');
    const params = new URLSearchParams({
      type: this.role,
      episodeId: this.episodeId,
      sessionId: this.sessionId,
      since: String(this.lastSeq),
    });
    if (this.token) params.set('token', this.token);
    if (this.appearanceId) params.set('appearanceId', this.appearanceId);
    return `${ws}/live/${this.episodeId}/ws?${params.toString()}`;
  }

  async connect(episodeId: string, opts: LiveConnectOptions = {}): Promise<void> {
    this.episodeId = episodeId;
    this.role = opts.role ?? 'stage';
    this.token = opts.token;
    this.appearanceId = opts.appearanceId;
    if (opts.sessionId) this.sessionId = opts.sessionId;
    if (opts.since !== undefined) this.lastSeq = opts.since;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;
    return this.open();
  }

  private open(): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false;
      const ws = new WebSocket(this.wsUrl());
      this.ws = ws;
      ws.onopen = () => {
        this.reconnectAttempts = 0;
        ws.send(JSON.stringify({ type: 'ready', last_seq: this.lastSeq }));
        if (!settled) { settled = true; resolve(); }
      };
      ws.onmessage = (ev: MessageEvent) => {
        try { this.handleMessage(JSON.parse(String(ev.data))); } catch { /* malformed frame */ }
      };
      ws.onerror = () => {
        if (!settled) { settled = true; reject(new Error('websocket failed')); }
      };
      ws.onclose = () => {
        if (this.ws === ws) this.ws = null;
        if (!this.shouldReconnect) return;
        const delay = Math.min(BACKOFF_BASE_MS * 2 ** this.reconnectAttempts, BACKOFF_MAX_MS);
        this.reconnectAttempts += 1;
        this.reconnectTimer = setTimeout(() => {
          this.reconnectTimer = null;
          if (this.shouldReconnect) void this.open().catch(() => {});
        }, delay);
      };
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      try { ws.close(); } catch { /* already gone */ }
    }
  }

  private handleMessage(data: any): void {
    const type = data?.type;
    if (type === 'show.snapshot') { this.handlers.snapshot(data.data ?? {}); return; }
    if (data?.data?.seq !== undefined && type !== 'crowd.update') {
      const ev = data.data as ShowEvent;
      this.lastSeq = Math.max(this.lastSeq, ev.seq);
      this.handlers.event(ev);
      return;
    }
    if (type === 'crowd.update') { this.handlers.crowd(data.data ?? {}); return; }
    if (type === 'auth.rejected') {
      this.handlers.rejected(String(data.data?.reason ?? 'rejected'));
      this.disconnect();
    }
  }

  // ── outgoing (socket) ────────────────────────────────────────────
  private send(obj: unknown): void {
    if (this.ws && this.ws.readyState === 1) this.ws.send(JSON.stringify(obj));
  }

  sendReaction(reaction: string, setTimeMs = 0, extra: Record<string, unknown> = {}): void {
    this.clientSeq += 1;
    this.send({ type: 'reaction', reaction, session_id: this.sessionId, client_seq: this.clientSeq, set_time_ms: setTimeMs, ...extra });
  }
  sendHeartbeat(): void { this.send({ type: 'heartbeat' }); }
  sendCameraCut(camera: string, setTimeMs = 0): void {
    this.send({ type: 'camera.cut', camera, set_time_ms: setTimeMs, source: 'human_director' });
  }
  sendStageAck(payload: Record<string, unknown>): void { this.send({ type: 'stage.ack', ...payload }); }

  // ── outgoing (HTTP commands) ─────────────────────────────────────
  async command(type: string, payload: Record<string, unknown> = {}, commandId?: string): Promise<CommandResult> {
    const res = await fetch(`${this.httpBase()}/live/${this.episodeId}/command`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(this.opts.authKey) },
      body: JSON.stringify({ commandId: commandId ?? `${type}-${Date.now()}-${Math.floor(Math.random() * 1e6)}`, type, payload }),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`command failed (${res.status}): ${text.slice(0, 160)}`);
    }
    return (await res.json()) as CommandResult;
  }

  async mintStageToken(role: 'stage' | 'puppeteer' = 'stage', ttlSec = 4 * 3600): Promise<string> {
    const res = await fetch(`${this.httpBase()}/live/${this.episodeId}/stage-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(this.opts.authKey) },
      body: JSON.stringify({ role, ttlSec }),
    });
    if (!res.ok) throw new Error(`mint failed (${res.status})`);
    const data = (await res.json()) as { token?: string };
    if (!data.token) throw new Error('no token in response');
    return data.token;
  }
}
