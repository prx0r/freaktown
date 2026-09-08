/**
 * EventConsumer — live socket to the EpisodeRoom Durable Object.
 *
 * - Roles: stage (HMAC token required), audience (session only).
 * - Reconnect: unexpected drops reconnect with capped exponential
 *   backoff; explicit disconnect() never reconnects (no zombies —
 *   React StrictMode mount/cleanup/mount is safe).
 * - Subscribers: the execution layer (StageEventExecutor) subscribes to
 *   raw events; the store reducer stays a pure state mirror.
 * - Audience messages carry stable session_id + monotonic client_seq +
 *   set_time_ms for the ML event log.
 */

import { useShowStore, ShowEvent, ShowPhase } from '../store/showStore';

export type ConsumerRole = 'stage' | 'audience';

export interface ConnectOptions {
  role?: ConsumerRole;
  /** HMAC stage token (required for role=stage). */
  token?: string;
  /** Stable audience session id (persisted by the caller in localStorage). */
  sessionId?: string;
  /** Resume from this seq (replay everything after it). */
  since?: number;
  appearanceId?: string;
}

export type EventHandler = (event: ShowEvent) => void;

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 15000;

export class EventConsumer {
  private store = useShowStore;
  private ws: WebSocket | null = null;
  private episodeId: string = '';
  private role: ConsumerRole = 'stage';
  private token?: string;
  private sessionId: string;
  private lastSeq: number = 0;
  private clientSeq: number = 0;

  private shouldReconnect = true;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempts = 0;

  private handlers = new Set<EventHandler>();

  constructor() {
    this.sessionId =
      typeof crypto !== 'undefined' && 'randomUUID' in crypto
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
  }

  // ── Subscriptions ────────────────────────────────────────────────

  onEvent(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => { this.handlers.delete(handler); };
  }

  private emit(event: ShowEvent): void {
    this.store.getState().applyEvent(event);
    this.lastSeq = Math.max(this.lastSeq, event.seq);
    for (const h of this.handlers) {
      try { h(event); } catch { /* subscriber errors never break the socket */ }
    }
  }

  // ── WebSocket Connection ─────────────────────────────────────────

  async connect(episodeId: string, opts: ConnectOptions = {}): Promise<void> {
    this.episodeId = episodeId;
    this.role = opts.role ?? 'stage';
    this.token = opts.token;
    if (opts.sessionId) this.sessionId = opts.sessionId;
    if (opts.since !== undefined) this.lastSeq = opts.since;
    this.shouldReconnect = true;
    this.reconnectAttempts = 0;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const params = new URLSearchParams({
      type: this.role,
      episodeId,
      sessionId: this.sessionId,
      since: String(this.lastSeq),
    });
    if (this.token) params.set('token', this.token);
    if (opts.appearanceId) params.set('appearanceId', opts.appearanceId);
    const url = `${protocol}//${host}/live/${episodeId}/ws?${params.toString()}`;

    return new Promise((resolve, reject) => {
      let settled = false;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.ws?.send(JSON.stringify({ type: 'ready', last_seq: this.lastSeq }));
        if (!settled) { settled = true; resolve(); }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch {
          // Malformed frames are ignored, never fatal.
        }
      };

      this.ws.onerror = () => {
        if (!settled) { settled = true; reject(new Error('websocket failed')); }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (!this.shouldReconnect) return;
        const delay = Math.min(BACKOFF_BASE_MS * 2 ** this.reconnectAttempts, BACKOFF_MAX_MS);
        this.reconnectAttempts += 1;
        this.reconnectTimer = setTimeout(() => {
          this.reconnectTimer = null;
          if (this.shouldReconnect) {
            void this.connect(episodeId, {
              role: this.role, token: this.token,
              sessionId: this.sessionId, since: this.lastSeq,
            });
          }
        }, delay);
      };
    });
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try { this.ws.close(); } catch { /* already gone */ }
      this.ws = null;
    }
  }

  get connected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  // ── Message Handling ─────────────────────────────────────────────

  private handleMessage(data: any): void {
    const { type } = data;

    if (type === 'show.snapshot') {
      this.handleSnapshot(data.data);
      return;
    }

    // Replayed + live events arrive as { type: 'show.event', data: {...} }
    if (type === 'show.event' && data.data?.seq !== undefined) {
      this.emit(data.data as ShowEvent);
      return;
    }

    // Legacy shape: event object inline
    if (data.data?.seq !== undefined) {
      this.emit(data.data as ShowEvent);
      return;
    }

    switch (type) {
      case 'crowd.update':
        this.store.getState().setCrowd(data.data);
        break;
      case 'auth.rejected':
        this.disconnect();
        break;
      case 'heartbeat.ack':
        break;
      default:
        break;
    }
  }

  private handleSnapshot(snapshot: any): void {
    const state = this.store.getState();
    // Canonical wire names are snake_case (freaktown.event.v1).
    // camelCase accepted transiently for backward compatibility.
    const episodeId = snapshot.episode_id ?? snapshot.episodeId;
    if (episodeId) state.setEpisode(episodeId);
    if (snapshot.phase) state.setPhase(snapshot.phase as ShowPhase);
    if (typeof snapshot.seq === 'number') {
      this.lastSeq = Math.max(this.lastSeq, snapshot.seq);
    }
  }

  // ── Outgoing ─────────────────────────────────────────────────────

  private nextClientSeq(): number {
    this.clientSeq += 1;
    return this.clientSeq;
  }

  sendReaction(reaction: string, setTimeMs = 0, extra: Record<string, any> = {}): void {
    this.ws?.send(JSON.stringify({
      type: 'reaction',
      reaction,
      session_id: this.sessionId,
      client_seq: this.nextClientSeq(),
      set_time_ms: setTimeMs,
      ...extra,
    }));
  }

  sendHeartbeat(): void {
    this.ws?.send(JSON.stringify({ type: 'heartbeat' }));
  }

  sendCameraCut(camera: string, setTimeMs = 0): void {
    this.ws?.send(JSON.stringify({
      type: 'camera.cut',
      camera,
      set_time_ms: setTimeMs,
      source: 'human_director',
    }));
  }

  sendStageAck(payload: Record<string, any>): void {
    this.ws?.send(JSON.stringify({ type: 'stage.ack', ...payload }));
  }
}
