/**
 * ControlClient — the ONLY way /control touches the show.
 *
 * Control never mutates stage state directly (its Zustand store is a
 * different page from the stage's). Every operator action is a canonical
 * command:
 *
 *   CONTROL → POST /live/:ep/command → EpisodeRoom → persist → broadcast
 *                                                         ↓
 *                                                   STAGE executes
 *
 * That invariant is what makes replay/ML possible later.
 * Auth: admin API key (X-API-Key) or Privy JWT (Bearer). Stored by the
 * page in localStorage; never in the URL.
 */

export interface CommandResult {
  status: string;
  event?: Record<string, unknown>;
}

function authHeaders(key: string): Record<string, string> {
  if (key.startsWith('ft_')) return { 'X-API-Key': key };
  return { Authorization: `Bearer ${key}` };
}

export class ControlClient {
  private episodeId: string;
  private key: string;

  constructor(episodeId: string, key: string) {
    this.episodeId = episodeId;
    this.key = key;
  }

  setKey(key: string): void {
    this.key = key;
  }

  private async post(path: string, body: unknown): Promise<CommandResult> {
    const res = await fetch(`/live/${this.episodeId}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(this.key) },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`command failed (${res.status}): ${text.slice(0, 160)}`);
    }
    return (await res.json()) as CommandResult;
  }

  command(type: string, payload: Record<string, unknown> = {}, commandId?: string): Promise<CommandResult> {
    return this.post('/command', {
      commandId: commandId ?? `${type}-${Date.now()}`,
      type,
      payload,
    });
  }

  // ── Show lifecycle ───────────────────────────────────────────────

  startShow(title?: string): Promise<CommandResult> {
    return this.command('show.start', title ? { title } : {});
  }

  pauseShow(): Promise<CommandResult> {
    return this.command('show.pause', {});
  }

  resumeShow(): Promise<CommandResult> {
    return this.command('show.resume', {});
  }

  endShow(): Promise<CommandResult> {
    return this.command('show.end', {});
  }

  setPhase(phase: string): Promise<CommandResult> {
    return this.command('show.phase', { phase });
  }

  // ── Performance ──────────────────────────────────────────────────

  preloadPerformance(opts: {
    performance_id: string;
    avatar_url: string;
    audio_url: string;
    plan?: unknown;
    word_timings?: unknown;
    walkout_url?: string;
  }): Promise<CommandResult> {
    return this.command('performance.preload', { ...opts });
  }

  startPerformance(performanceId: string): Promise<CommandResult> {
    return this.command('performance.start', { performance_id: performanceId });
  }

  endPerformance(performanceId: string): Promise<CommandResult> {
    return this.command('performance.end', { performance_id: performanceId });
  }

  enterCharacter(appearanceId: string): Promise<CommandResult> {
    return this.command('character.enter', { appearanceId });
  }

  exitCharacter(appearanceId: string): Promise<CommandResult> {
    return this.command('character.exit', { appearanceId });
  }

  // ── Camera (originates here; the stage merely executes) ──────────

  cutCamera(camera: string, setTimeMs = 0): Promise<CommandResult> {
    return this.command('camera.cut', {
      camera,
      set_time_ms: setTimeMs,
      source: 'human_director',
    });
  }

  // ── Judges ───────────────────────────────────────────────────────

  revealScores(): Promise<CommandResult> {
    return this.command('judge.reveal', {});
  }

  // ── Stage token ──────────────────────────────────────────────────

  async mintStageToken(role: 'stage' | 'puppeteer' = 'stage', ttlSec = 4 * 3600): Promise<string> {
    const res = await fetch(`/live/${this.episodeId}/stage-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(this.key) },
      body: JSON.stringify({ role, ttlSec }),
    });
    if (!res.ok) {
      throw new Error(`mint failed (${res.status})`);
    }
    const data = (await res.json()) as { token?: string };
    if (!data.token) throw new Error('no token in response');
    return data.token;
  }
}
