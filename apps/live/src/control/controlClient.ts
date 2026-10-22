/**
 * ControlClient — the ONLY way /control touches the show.
 *
 * Control never mutates stage state directly. Every operator action is a
 * canonical command through the ONE LiveTransport:
 *
 *   CONTROL → transport.command() → room (EpisodeRoom DO | LocalRoom)
 *           → persist → broadcast → STAGE executes
 *
 * That invariant is what makes replay/ML possible later.
 */

import type { CommandResult, LiveTransport } from '@funnier/stage-runtime';
import { EpisodeRoomTransport } from '@funnier/stage-runtime';

export type { CommandResult };

export class ControlClient {
  private transport: LiveTransport;

  constructor(transport: LiveTransport) {
    this.transport = transport;
  }

  command(type: string, payload: Record<string, unknown> = {}, commandId?: string): Promise<CommandResult> {
    return this.transport.command(type, payload, commandId);
  }

  // ── Show lifecycle ───────────────────────────────────────────────
  startShow(title?: string) { return this.command('show.start', title ? { title } : {}); }
  pauseShow() { return this.command('show.pause', {}); }
  resumeShow() { return this.command('show.resume', {}); }
  endShow() { return this.command('show.end', {}); }
  setPhase(phase: string) { return this.command('show.phase', { phase }); }

  // ── Performance ──────────────────────────────────────────────────
  preloadPerformance(opts: {
    performance_id: string;
    avatar_url: string;
    audio_url: string;
    set_url?: string;
    plan?: unknown;
    word_timings?: unknown;
    walkout_url?: string;
    character_name?: string;
    title?: string;
    episode_id?: string;
  }) { return this.command('performance.preload', { ...opts }); }
  startPerformance(performanceId: string) { return this.command('performance.start', { performance_id: performanceId }); }
  endPerformance(performanceId: string) { return this.command('performance.end', { performance_id: performanceId }); }
  enterCharacter(appearanceId: string) { return this.command('character.enter', { appearanceId }); }
  exitCharacter(appearanceId: string) { return this.command('character.exit', { appearanceId }); }

  // ── Camera (originates here; the stage merely executes) ──────────
  cutCamera(camera: string, setTimeMs = 0) {
    return this.command('camera.cut', { camera, set_time_ms: setTimeMs, source: 'human_director' });
  }

  // ── Crowd (operator-triggered reaction → stage sfx + room energy) ─
  triggerReaction(reaction: string, setTimeMs = 0) {
    return this.command('crowd.reaction', { reaction, set_time_ms: setTimeMs, source: 'operator' });
  }
  playSfx(name: string) { return this.command('audio.sfx.play', { name }); }

  // ── Judges ───────────────────────────────────────────────────────
  revealScores() { return this.command('judge.reveal', {}); }

  // ── Stage token (EpisodeRoom only) ───────────────────────────────
  async mintStageToken(role: 'stage' | 'puppeteer' = 'stage', ttlSec = 4 * 3600): Promise<string | null> {
    if (this.transport instanceof EpisodeRoomTransport) return this.transport.mintStageToken(role, ttlSec);
    return null; // local link needs no token
  }
}
