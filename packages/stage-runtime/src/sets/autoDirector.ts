/**
 * Active-speaker auto director (pure). Dialogue lines in, camera cues out.
 *   speaker changes        → single of the new speaker (close every 3rd line)
 *   quick back-and-forth   → two-shot of the last two speakers
 *   silence > idleMs       → the set's wide
 * Never cuts faster than minCutMs and never repeats the current shot.
 */
export interface AutoDirectorOptions { minCutMs?: number; idleMs?: number; wide?: string }

export class ActiveSpeakerDirector {
  private last = '';
  private lastCutAt = -Infinity;
  private speakers: string[] = [];
  private lines = 0;
  private lastLineAt = -Infinity;
  private lastLineEnd = -Infinity;
  private opts: Required<AutoDirectorOptions>;

  constructor(opts: AutoDirectorOptions = {}) {
    this.opts = { minCutMs: 1200, idleMs: 4000, wide: 'wide', ...opts };
  }

  get current(): string { return this.last; }

  /** Reset to a shot chosen elsewhere (operator cut or set load). */
  note(cue: string, atMs: number): void { this.last = cue; this.lastCutAt = atMs; }

  onLine(seat: string, atMs: number, durationMs = 2000): string | null {
    const prev = this.speakers[this.speakers.length - 1];
    const gap = atMs - this.lastLineEnd;
    this.lines++;
    this.lastLineAt = atMs;
    this.lastLineEnd = atMs + durationMs;
    if (prev !== seat) this.speakers.push(seat);
    if (this.speakers.length > 6) this.speakers.shift();
    let cue: string;
    if (prev && prev !== seat && gap < 300 && durationMs < 1800) cue = `two-shot:${prev}+${seat}`;
    else cue = this.lines % 3 === 0 ? `close:${seat}` : `single:${seat}`;
    return this.cut(cue, atMs);
  }

  tick(nowMs: number): string | null {
    if (nowMs - this.lastLineEnd > this.opts.idleMs && this.lastLineAt > -Infinity && this.last !== this.opts.wide) {
      return this.cut(this.opts.wide, nowMs);
    }
    return null;
  }

  private cut(cue: string, atMs: number): string | null {
    if (cue === this.last) return null;
    if (atMs - this.lastCutAt < this.opts.minCutMs) return null;
    this.last = cue;
    this.lastCutAt = atMs;
    return cue;
  }
}
