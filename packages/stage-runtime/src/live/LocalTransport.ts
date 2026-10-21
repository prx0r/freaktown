/**
 * LocalTransport — LiveTransport without Cloudflare.
 *
 * Every tab on the same origin shares one LocalRoom (localStorage log)
 * and one BroadcastChannel (`ft-live:<episode>`). Commands from /control
 * persist into the log and fan out to /stage tabs exactly like the DO.
 * A stage tab opened late replays the log (snapshot + events > since).
 */

import type { ShowEvent } from '@freaktown/contracts';
import {
  HandlerSet, newSessionId,
  type CommandResult, type LiveConnectOptions, type LiveHandlers, type LiveRole, type LiveTransport,
} from './LiveTransport';
import { LocalRoom, memoryStorage, type ChannelLike, type KeyValueStorage, type RoomWire } from './LocalRoom';

export interface LocalTransportOptions {
  storage?: KeyValueStorage;
  channelFactory?: (name: string) => ChannelLike;
}

function defaultStorage(): KeyValueStorage {
  try {
    if (typeof localStorage !== 'undefined') return localStorage;
  } catch { /* privacy mode */ }
  return memoryStorage();
}

function defaultChannel(name: string): ChannelLike {
  return new BroadcastChannel(name) as unknown as ChannelLike;
}

export class LocalTransport implements LiveTransport {
  readonly kind = 'local' as const;
  private room: LocalRoom | null = null;
  private channel: ChannelLike | null = null;
  private handlers = new HandlerSet();
  private role: LiveRole = 'stage';
  private sessionId = newSessionId();
  private lastSeq = 0;
  private storage: KeyValueStorage;
  private channelFactory: (name: string) => ChannelLike;
  private listener = (ev: { data: unknown }) => this.onWire(ev.data as RoomWire);

  constructor(opts: LocalTransportOptions = {}) {
    this.storage = opts.storage ?? defaultStorage();
    this.channelFactory = opts.channelFactory ?? defaultChannel;
  }

  get connected(): boolean { return this.channel !== null; }

  /** The underlying room (control uses it for reset/inspection). */
  get localRoom(): LocalRoom | null { return this.room; }

  subscribe(h: LiveHandlers): () => void { return this.handlers.add(h); }

  async connect(episodeId: string, opts: LiveConnectOptions = {}): Promise<void> {
    this.disconnect();
    this.role = opts.role ?? 'stage';
    if (opts.sessionId) this.sessionId = opts.sessionId;
    this.lastSeq = opts.since ?? 0;
    this.room = new LocalRoom(episodeId, this.storage);
    this.channel = this.channelFactory(`ft-live:${episodeId}`);
    this.channel.addEventListener('message', this.listener);
    // ready → snapshot + replay, like EpisodeRoom.handleReady
    queueMicrotask(() => {
      if (!this.room) return;
      this.handlers.snapshot(this.room.snapshot());
      for (const e of this.room.replay(this.lastSeq)) this.deliver(e);
    });
  }

  disconnect(): void {
    if (this.channel) {
      this.channel.removeEventListener('message', this.listener);
      try { this.channel.close(); } catch { /* closed */ }
    }
    this.channel = null;
  }

  private deliver(e: ShowEvent): void {
    if (e.seq <= this.lastSeq) return; // replay/duplicate safe
    this.lastSeq = e.seq;
    this.handlers.event(e);
  }

  private onWire(msg: RoomWire): void {
    if (!msg || typeof msg !== 'object') return;
    if (msg.type === 'show.event') {
      // Fill any gap from storage (missed broadcast while busy).
      if (this.room && msg.data.seq > this.lastSeq + 1) {
        for (const e of this.room.replay(this.lastSeq)) this.deliver(e);
      }
      this.deliver(msg.data);
    } else if (msg.type === 'crowd.update') {
      this.handlers.crowd(msg.data);
    } else if (msg.type === 'room.reset') {
      this.lastSeq = 0;
      if (this.room) this.handlers.snapshot(this.room.snapshot());
    }
  }

  private broadcast(msg: RoomWire): void {
    try { this.channel?.postMessage(msg); } catch { /* closed */ }
    // BroadcastChannel never echoes to the sender: deliver locally too.
    this.onWire(msg);
  }

  private requireRoom(): LocalRoom {
    if (!this.room) throw new Error('LocalTransport not connected');
    return this.room;
  }

  async command(type: string, payload: Record<string, unknown> = {}, commandId?: string): Promise<CommandResult> {
    const res = this.requireRoom().execute(type, payload, commandId);
    if (res.status === 'rejected') throw new Error(`command rejected: ${res.error}`);
    if (res.event) this.broadcast({ type: 'show.event', data: res.event });
    return { status: res.status, event: res.event, seq: res.seq };
  }

  sendStageAck(payload: Record<string, unknown>): void {
    if (this.role !== 'stage' || !this.room) return;
    const { event, ...rest } = payload as { event?: unknown };
    if (typeof event !== 'string' || !event) return;
    const res = this.room.execute(event, { actor: 'stage', ...rest });
    if (res.event) this.broadcast({ type: 'show.event', data: res.event });
  }

  sendReaction(reaction: string): void {
    if (!this.room) return;
    const s = this.room.state;
    if (!s.activeAppearanceId || s.isPaused) return; // DO rule: only while on stage
    const crowd = this.room.react(reaction, this.sessionId);
    if (crowd) this.broadcast({ type: 'crowd.update', data: crowd });
  }

  sendCameraCut(camera: string, setTimeMs = 0): void {
    if (this.role === 'audience' || !this.room) return;
    const res = this.room.execute('camera.cut', {
      actor: this.role, camera, set_time_ms: setTimeMs, source: 'human_director',
    });
    if (res.event) this.broadcast({ type: 'show.event', data: res.event });
  }

  sendHeartbeat(): void { /* local link has no liveness to prove */ }

  /** Wipe the episode log (control "new show"). Broadcasts room.reset. */
  reset(): void {
    this.requireRoom().reset();
    this.broadcast({ type: 'room.reset', data: { episode_id: this.room!.episodeId } });
  }
}
