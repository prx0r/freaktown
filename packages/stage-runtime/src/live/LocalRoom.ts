/**
 * LocalRoom — offline EpisodeRoom. Same semantics as the Durable Object:
 *   persist BEFORE broadcast · monotonic seq · idempotent commandId ·
 *   snapshot + replay(since) on ready · shared applyEpisodeEvent reducer.
 *
 * Storage and channel are injected so it runs in a browser
 * (localStorage + BroadcastChannel, shared by every tab on the origin)
 * and in vitest (memory storage + node BroadcastChannel).
 */

import {
  applyEpisodeEvent, initialEpisodeState, validateCameraCut,
  type EpisodeState, type ShowEvent,
} from '@freaktown/contracts';

export interface KeyValueStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface ChannelLike {
  postMessage(msg: unknown): void;
  addEventListener(type: 'message', fn: (ev: { data: unknown }) => void): void;
  removeEventListener(type: 'message', fn: (ev: { data: unknown }) => void): void;
  close(): void;
}

export type RoomWire =
  | { type: 'show.event'; data: ShowEvent }
  | { type: 'crowd.update'; data: Record<string, number> }
  | { type: 'room.reset'; data: { episode_id: string } };

export function memoryStorage(): KeyValueStorage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => (m.has(k) ? (m.get(k) as string) : null),
    setItem: (k, v) => { m.set(k, v); },
    removeItem: (k) => { m.delete(k); },
  };
}

const SUPPORTED_REACTIONS = new Set(['laugh', 'clap', 'boo', 'crickets', 'groan', 'love', 'wtf']);

export class LocalRoom {
  readonly episodeId: string;
  private storage: KeyValueStorage;
  private prefix: string;

  constructor(episodeId: string, storage: KeyValueStorage) {
    this.episodeId = episodeId;
    this.storage = storage;
    this.prefix = `ft-live:${episodeId}:`;
  }

  // ── storage ──────────────────────────────────────────────────────
  private read<T>(key: string, fallback: T): T {
    const raw = this.storage.getItem(this.prefix + key);
    if (raw == null) return fallback;
    try { return JSON.parse(raw) as T; } catch { return fallback; }
  }
  private write(key: string, value: unknown): void {
    this.storage.setItem(this.prefix + key, JSON.stringify(value));
  }

  get state(): EpisodeState {
    return this.read<EpisodeState>('state', initialEpisodeState(this.episodeId));
  }

  get log(): ShowEvent[] {
    return this.read<ShowEvent[]>('log', []);
  }

  snapshot() {
    const s = this.state;
    return {
      episode_id: s.episodeId || this.episodeId,
      phase: s.phase,
      active_appearance_id: s.activeAppearanceId,
      seq: s.seq,
      is_paused: s.isPaused,
    };
  }

  /** Events with seq > since, in order (reconnect replay). */
  replay(since = 0): ShowEvent[] {
    return this.log.filter((e) => e.seq > since).sort((a, b) => a.seq - b.seq);
  }

  // ── commands (persist before broadcast; caller broadcasts) ────────
  /**
   * `known`: events this tab already saw on the BroadcastChannel. Another tab's
   * localStorage write can lag its broadcast (separate renderer processes), so a
   * writer reacting to a just-broadcast event (e.g. the dealer answering a
   * /play poker.intent) merges what it saw instead of reusing a stale seq.
   */
  execute(type: string, payload: Record<string, unknown> = {}, commandId?: string, known: ShowEvent[] = []):
    { status: 'ok' | 'already_executed' | 'rejected'; event?: ShowEvent; seq?: number; error?: string } {
    if (!type) return { status: 'rejected', error: 'type required' };
    const cmds = this.read<Record<string, number>>('cmds', {});
    if (commandId && cmds[commandId] !== undefined) {
      return { status: 'already_executed', seq: cmds[commandId] };
    }
    if (type === 'camera.cut') {
      // Same gate as the DO: unknown cameras are never persisted.
      const parsed = validateCameraCut({ source: 'human_director', ...payload });
      if (!parsed.ok) return { status: 'rejected', error: parsed.error };
      payload = { ...payload, ...parsed.value };
    }
    const state = this.state;
    if (!state.episodeId) state.episodeId = this.episodeId;
    const log = this.log;
    const top = log.length ? log[log.length - 1].seq : 0;
    const missing = known.filter((e) => e.seq > top && !log.some((x) => x.seq === e.seq)).sort((a, b) => a.seq - b.seq);
    for (const e of missing) log.push(e);
    state.seq = Math.max(state.seq, log.length ? log[log.length - 1].seq : 0);
    state.seq += 1;
    const event: ShowEvent = {
      seq: state.seq,
      type,
      actor: (payload.actor as string) || 'system',
      payload,
      created_at: new Date().toISOString(),
    };
    log.push(event);
    this.write('log', log);                       // 1. persist event
    applyEpisodeEvent(state, type, payload, event.created_at);
    this.write('state', state);                   // 2. persist state
    if (commandId) { cmds[commandId] = event.seq; this.write('cmds', cmds); }
    return { status: 'ok', event, seq: event.seq }; // 3. caller broadcasts
  }

  /** Audience reaction → raw persisted record + derived crowd aggregate. */
  react(reaction: string, sessionId: string): Record<string, number> | null {
    if (!SUPPORTED_REACTIONS.has(reaction)) return null;
    const crowd = this.read<Record<string, number> & { sessions?: never }>('crowd', {
      laugh_events: 0, claps: 0, boos: 0, crickets: 0, groans: 0, unique_laughers: 0,
    });
    const laughers = this.read<string[]>('laughers', []);
    if (reaction === 'laugh') {
      crowd.laugh_events += 1;
      if (!laughers.includes(sessionId)) { laughers.push(sessionId); this.write('laughers', laughers); }
      crowd.unique_laughers = laughers.length;
    } else if (reaction === 'clap') crowd.claps += 1;
    else if (reaction === 'boo') crowd.boos += 1;
    else if (reaction === 'crickets') crowd.crickets += 1;
    else if (reaction === 'groan') crowd.groans += 1;
    this.write('crowd', crowd);
    return crowd;
  }

  reset(): void {
    for (const k of ['state', 'log', 'cmds', 'crowd', 'laughers']) {
      this.storage.removeItem(this.prefix + k);
    }
  }
}
