/**
 * EventConsumer — the stage's (and any viewer's) inbound event pipe.
 *
 * Transport-agnostic: rides a LiveTransport (EpisodeRoom websocket or
 * offline LocalTransport). Feeds an injected RoomStore (pure state mirror)
 * and fans raw events out to subscribers (StageEventExecutor).
 *
 * - Dedup: handlers see each seq once (replay + duplicate delivery safe).
 * - Snapshot seq never advances the dedup mark: replay arrives AFTER the
 *   snapshot and must still execute.
 * - Audience messages carry stable session_id + monotonic client_seq +
 *   set_time_ms for the ML event log (delegated to the transport).
 */

import type { ShowEvent, ShowPhase } from '@freaktown/contracts';
import type { RoomStore } from './ports';
import type { LiveConnectOptions, LiveSnapshot, LiveTransport } from './live/LiveTransport';
import { EpisodeRoomTransport } from './live/EpisodeRoomTransport';

export type ConsumerRole = 'stage' | 'audience';
export type ConnectOptions = LiveConnectOptions;
export type EventHandler = (event: ShowEvent) => void;

export interface EventConsumerOptions {
  transport?: LiveTransport;
  store?: RoomStore;
}

export class EventConsumer {
  readonly transport: LiveTransport;
  private store?: RoomStore;
  private lastAppliedSeq = 0;
  private handlers = new Set<EventHandler>();
  private snapshotHandlers = new Set<(s: LiveSnapshot) => void>();
  private unsubscribe: (() => void) | null = null;

  constructor(opts: EventConsumerOptions = {}) {
    this.transport = opts.transport ?? new EpisodeRoomTransport();
    this.store = opts.store;
  }

  setStore(store: RoomStore | undefined): void { this.store = store; }

  onEvent(handler: EventHandler): () => void {
    this.handlers.add(handler);
    return () => { this.handlers.delete(handler); };
  }

  onSnapshot(handler: (s: LiveSnapshot) => void): () => void {
    this.snapshotHandlers.add(handler);
    return () => { this.snapshotHandlers.delete(handler); };
  }

  get lastSeq(): number { return this.lastAppliedSeq; }

  private emit(event: ShowEvent): void {
    if (typeof event.seq !== 'number' || event.seq <= this.lastAppliedSeq) return;
    this.lastAppliedSeq = event.seq;
    try { this.store?.applyEvent(event); } catch { /* store errors never break the pipe */ }
    for (const h of this.handlers) {
      try { h(event); } catch { /* subscriber errors never break the pipe */ }
    }
  }

  private handleSnapshot(snapshot: LiveSnapshot & { episodeId?: string }): void {
    const episodeId = snapshot.episode_id ?? snapshot.episodeId;
    if (episodeId) this.store?.setEpisode(episodeId);
    if (snapshot.phase) this.store?.setPhase(snapshot.phase as ShowPhase);
    if (snapshot.seq === 0) this.lastAppliedSeq = 0; // room was reset
    for (const h of this.snapshotHandlers) {
      try { h(snapshot); } catch { /* ignore */ }
    }
  }

  async connect(episodeId: string, opts: ConnectOptions = {}): Promise<void> {
    this.unsubscribe?.();
    this.unsubscribe = this.transport.subscribe({
      onEvent: (e) => this.emit(e),
      onSnapshot: (s) => this.handleSnapshot(s),
      onCrowd: (c) => this.store?.setCrowd(c),
    });
    await this.transport.connect(episodeId, { since: this.lastAppliedSeq, ...opts });
  }

  disconnect(): void {
    this.transport.disconnect();
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  get connected(): boolean { return this.transport.connected; }

  // ── outgoing (delegated) ─────────────────────────────────────────
  sendReaction(reaction: string, setTimeMs = 0, extra: Record<string, unknown> = {}): void {
    this.transport.sendReaction(reaction, setTimeMs, extra);
  }
  sendHeartbeat(): void { this.transport.sendHeartbeat(); }
  sendCameraCut(camera: string, setTimeMs = 0): void { this.transport.sendCameraCut(camera, setTimeMs); }
  sendStageAck(payload: Record<string, unknown>): void { this.transport.sendStageAck(payload); }
}
