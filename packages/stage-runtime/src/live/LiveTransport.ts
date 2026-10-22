/**
 * LiveTransport — the ONE seam between pages and a show room.
 *
 * Two implementations, same contract:
 *   - EpisodeRoomTransport: Cloudflare EpisodeRoom DO (websocket + POST
 *     /live/:ep/command). Production / `wrangler dev`.
 *   - LocalTransport: BroadcastChannel + localStorage log, running the
 *     same pure reducer (applyEpisodeEvent). Offline, no Cloudflare.
 *
 * Invariant (replay): control only calls command(); the stage only
 * reacts to events it receives. Nothing mutates the stage directly.
 */

import type { ShowEvent } from '@funnier/contracts';

export type LiveRole = 'stage' | 'audience' | 'puppeteer';

export interface LiveConnectOptions {
  role?: LiveRole;
  /** HMAC stage token (EpisodeRoom; required for role=stage). */
  token?: string;
  sessionId?: string;
  /** Replay everything after this seq. */
  since?: number;
  appearanceId?: string;
}

export interface LiveSnapshot {
  episode_id?: string;
  phase?: string;
  active_appearance_id?: string | null;
  seq?: number;
  is_paused?: boolean;
}

export interface LiveHandlers {
  onEvent?(event: ShowEvent): void;
  onSnapshot?(snapshot: LiveSnapshot): void;
  onCrowd?(crowd: Record<string, number>): void;
  onRejected?(reason: string): void;
}

export interface CommandResult {
  status: string;
  event?: ShowEvent | Record<string, unknown>;
  seq?: number;
}

export interface LiveTransport {
  readonly kind: 'episode-room' | 'local';
  readonly connected: boolean;
  connect(episodeId: string, opts?: LiveConnectOptions): Promise<void>;
  disconnect(): void;
  subscribe(handlers: LiveHandlers): () => void;
  /** Operator command → persisted event → broadcast (control path). */
  command(type: string, payload?: Record<string, unknown>, commandId?: string): Promise<CommandResult>;
  /** Stage readiness/completion ACK over the stage's own link. */
  sendStageAck(payload: Record<string, unknown>): void;
  sendReaction(reaction: string, setTimeMs?: number, extra?: Record<string, unknown>): void;
  sendCameraCut(camera: string, setTimeMs?: number): void;
  sendHeartbeat(): void;
}

export function newSessionId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `s-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
}

/** Small fan-out helper shared by both transports. */
export class HandlerSet {
  private set = new Set<LiveHandlers>();
  add(h: LiveHandlers): () => void {
    this.set.add(h);
    return () => { this.set.delete(h); };
  }
  event(e: ShowEvent): void { for (const h of this.set) safe(() => h.onEvent?.(e)); }
  snapshot(s: LiveSnapshot): void { for (const h of this.set) safe(() => h.onSnapshot?.(s)); }
  crowd(c: Record<string, number>): void { for (const h of this.set) safe(() => h.onCrowd?.(c)); }
  rejected(r: string): void { for (const h of this.set) safe(() => h.onRejected?.(r)); }
}

function safe(fn: () => void): void {
  try { fn(); } catch { /* subscriber errors never break the link */ }
}
