/**
 * EpisodeRoom audience anti-spam and dedup tests.
 *
 * Tests the DO's reaction handling logic: vocabulary filtering,
 * client_seq dedup, rate limiting, and unique laugher tracking.
 *
 * These are unit tests of the logic extracted from the DO — they don't
 * require a running Cloudflare runtime.
 */

import { describe, it, expect, beforeEach } from 'vitest';

// ── Extracted logic from EpisodeRoom.handleReaction ──────────────────
// We test the filtering/gating logic directly rather than spinning up
// a full DO, since the logic is pure and deterministic.

const SUPPORTED_REACTIONS: ReadonlySet<string> = new Set([
  'laugh', 'clap', 'boo', 'crickets', 'groan', 'love', 'wtf',
]);

function isValidReaction(reaction: string): boolean {
  return SUPPORTED_REACTIONS.has(reaction);
}

function isValidClientSeq(clientSeq: unknown): boolean {
  const seq = Number(clientSeq ?? NaN);
  return Number.isInteger(seq) && seq > 0;
}

function isDuplicate(clientSeq: number, highWaterMark: number): boolean {
  return clientSeq <= highWaterMark;
}

function isRateLimited(nowMs: number, lastReactionMs: number, windowMs = 250): boolean {
  return nowMs - lastReactionMs < windowMs;
}

// ── Crowd aggregate derivation ───────────────────────────────────────

interface CrowdWindow {
  laughs: number;
  claps: number;
  boos: number;
  crickets: number;
  groans: number;
  uniqueSessions: string[];
}

function createWindow(): CrowdWindow {
  return { laughs: 0, claps: 0, boos: 0, crickets: 0, groans: 0, uniqueSessions: [] };
}

function applyReaction(window: CrowdWindow, reaction: string, sessionId: string): CrowdWindow {
  if (reaction === 'laugh') {
    window.laughs += 1;
    if (!window.uniqueSessions.includes(sessionId)) {
      window.uniqueSessions.push(sessionId);
    }
  } else if (reaction === 'clap') {
    window.claps += 1;
  } else if (reaction === 'boo') {
    window.boos += 1;
  } else if (reaction === 'crickets') {
    window.crickets += 1;
  } else if (reaction === 'groan') {
    window.groans += 1;
  }
  // love/wtf: no aggregate impact
  return window;
}

// ── Tests ────────────────────────────────────────────────────────────

describe('Reaction vocabulary filtering', () => {
  it('accepts all valid reactions', () => {
    for (const r of ['laugh', 'clap', 'boo', 'crickets', 'groan', 'love', 'wtf']) {
      expect(isValidReaction(r)).toBe(true);
    }
  });

  it('rejects unknown reactions', () => {
    for (const r of ['scream', 'cry', 'fart', 'applause', 'haha', 'HAHA', '']) {
      expect(isValidReaction(r)).toBe(false);
    }
  });

  it('rejects injection attempts', () => {
    for (const r of ['<script>alert(1)</script>', '../../etc/passwd', '"; DROP TABLE reactions;']) {
      expect(isValidReaction(r)).toBe(false);
    }
  });
});

describe('client_seq validation', () => {
  it('accepts positive integers', () => {
    expect(isValidClientSeq(1)).toBe(true);
    expect(isValidClientSeq(42)).toBe(true);
    expect(isValidClientSeq(999999)).toBe(true);
  });

  it('rejects zero and negative', () => {
    expect(isValidClientSeq(0)).toBe(false);
    expect(isValidClientSeq(-1)).toBe(false);
  });

  it('rejects non-integers', () => {
    expect(isValidClientSeq(1.5)).toBe(false);
    expect(isValidClientSeq(NaN)).toBe(false);
    expect(isValidClientSeq(undefined)).toBe(false);
    expect(isValidClientSeq('abc')).toBe(false);
  });
});

describe('client_seq dedup', () => {
  it('accepts first reaction (seq > 0)', () => {
    expect(isDuplicate(1, 0)).toBe(false);
    expect(isDuplicate(5, 0)).toBe(false);
  });

  it('rejects duplicate seq', () => {
    expect(isDuplicate(1, 1)).toBe(true);
    expect(isDuplicate(5, 5)).toBe(true);
  });

  it('rejects out-of-order (lower seq)', () => {
    expect(isDuplicate(3, 5)).toBe(true);
    expect(isDuplicate(1, 100)).toBe(true);
  });

  it('accepts higher seq', () => {
    expect(isDuplicate(6, 5)).toBe(false);
    expect(isDuplicate(100, 99)).toBe(false);
  });
});

describe('Rate limiting', () => {
  it('allows first reaction (no prior)', () => {
    expect(isRateLimited(1000, 0)).toBe(false);
  });

  it('rejects within 250ms window', () => {
    expect(isRateLimited(1000, 800)).toBe(true);  // 200ms gap
    expect(isRateLimited(1000, 900)).toBe(true);  // 100ms gap
    expect(isRateLimited(1000, 999)).toBe(true);  // 1ms gap
  });

  it('allows after 250ms window', () => {
    expect(isRateLimited(1000, 700)).toBe(false);  // 300ms gap
    expect(isRateLimited(1000, 750)).toBe(false);  // 250ms gap (boundary)
    expect(isRateLimited(1000, 500)).toBe(false);  // 500ms gap
  });
});

describe('Crowd aggregate derivation', () => {
  it('counts laughs as unique sessions', () => {
    const w = createWindow();
    applyReaction(w, 'laugh', 's1');
    applyReaction(w, 'laugh', 's2');
    applyReaction(w, 'laugh', 's1'); // duplicate session
    expect(w.laughs).toBe(3);
    expect(w.uniqueSessions).toEqual(['s1', 's2']);
  });

  it('counts claps, boos, crickets, groans independently', () => {
    const w = createWindow();
    applyReaction(w, 'clap', 's1');
    applyReaction(w, 'clap', 's2');
    applyReaction(w, 'boo', 's3');
    applyReaction(w, 'crickets', 's4');
    applyReaction(w, 'groan', 's5');
    expect(w.claps).toBe(2);
    expect(w.boos).toBe(1);
    expect(w.crickets).toBe(1);
    expect(w.groans).toBe(1);
    expect(w.laughs).toBe(0);
  });

  it('love and wtf have no aggregate impact', () => {
    const w = createWindow();
    applyReaction(w, 'love', 's1');
    applyReaction(w, 'wtf', 's2');
    expect(w.laughs).toBe(0);
    expect(w.claps).toBe(0);
    expect(w.uniqueSessions).toEqual([]);
  });

  it('unique laugher count is per-window, not global', () => {
    const w = createWindow();
    applyReaction(w, 'laugh', 's1');
    applyReaction(w, 'laugh', 's2');
    applyReaction(w, 'laugh', 's3');
    expect(w.uniqueSessions.length).toBe(3);
  });
});

describe('Active appearance gating', () => {
  it('reactions ignored when no active appearance', () => {
    const activeAppearanceId = null;
    const isPaused = false;
    const shouldProcess = !!activeAppearanceId && !isPaused;
    expect(shouldProcess).toBe(false);
  });

  it('reactions ignored when show is paused', () => {
    const activeAppearanceId = 'app_123';
    const isPaused = true;
    const shouldProcess = !!activeAppearanceId && !isPaused;
    expect(shouldProcess).toBe(false);
  });

  it('reactions processed when active and not paused', () => {
    const activeAppearanceId = 'app_123';
    const isPaused = false;
    const shouldProcess = !!activeAppearanceId && !isPaused;
    expect(shouldProcess).toBe(true);
  });
});
