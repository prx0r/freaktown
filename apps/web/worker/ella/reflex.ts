/**
 * EllaReflex — Tier 0 deterministic reactions (<100ms, no LLM).
 *
 * Pure function over consecutive EllaSense snapshots (+ optional recent
 * event types). Runs at the edge next to EpisodeRoom: sense in, zero or
 * more ella.action candidates out. Every output carries latency_ms: 0
 * (local rules, no model call) and source reflex-v1, and becomes a
 * persisted ella.action event downstream — training data for free.
 *
 * Triggers: laugh spike, dead silence, big tip, wtf spike, ChatGPT
 * score reveal. Micro-lines rotate deterministically by seq (testable,
 * replayable — never Math.random in the hot path).
 */

import type { EllaSenseV1 } from '../../src/contracts/show';

export interface ReflexConfig {
  /** laughs/sec marking a spike */
  laughSpikePerSec: number;
  /** seconds of zero laughs during a set marking silence */
  silenceSec: number;
  /** pot delta (cents) marking a big tip */
  bigTipCents: number;
  /** groans+boos per sec marking a wtf spike */
  wtfPerSec: number;
}

export const DEFAULT_REFLEX_CONFIG: ReflexConfig = {
  laughSpikePerSec: 5,
  silenceSec: 8,
  bigTipCents: 10000, // $100
  wtfPerSec: 3,
};

export interface ReflexAction {
  trigger: string;
  action: string;
  latency_ms: 0;
  source: 'reflex-v1';
  text?: string;
  set_time_ms: number | null;
}

const MICRO_LINES = [
  'oh.',
  'Jesus.',
  'Okay.',
  'Interesting.',
  'Sure.',
  'Right.',
  'Wow.',
  'Hm.',
  'Oh no.',
  'Beautiful.',
  'Continue.',
  'Noted.',
];

export function microLine(seq: number): string {
  return MICRO_LINES[seq % MICRO_LINES.length];
}

export interface ReflexInput {
  prev: EllaSenseV1 | null;
  curr: EllaSenseV1;
  /** unix ms clock; injectable for tests */
  nowMs?: number;
  /** recent show event types (e.g. judge.chatgpt.locked) */
  recentEventTypes?: string[];
}

function perSec(curr: number, prev: number, dtSec: number): number {
  if (dtSec <= 0) return 0;
  return Math.max(0, curr - prev) / dtSec;
}

export function evaluateReflex(input: ReflexInput, config: ReflexConfig = DEFAULT_REFLEX_CONFIG): ReflexAction[] {
  const { prev, curr, recentEventTypes = [] } = input;
  const out: ReflexAction[] = [];
  if (curr.is_paused || !curr.active_appearance_id) return out;

  const nowMs = input.nowMs ?? Date.parse(curr.updated_at);
  const prevAt = prev ? Date.parse(prev.updated_at) : nowMs;
  const dtSec = Math.max(0, (nowMs - prevAt) / 1000);

  const laughVel = prev ? perSec(curr.crowd.laugh_events, prev.crowd.laugh_events, dtSec) : 0;
  const wtfVel = prev
    ? perSec(
        curr.crowd.groans + curr.crowd.boos,
        prev.crowd.groans + prev.crowd.boos,
        dtSec
      )
    : 0;
  const potDelta = prev ? curr.pot_cents - prev.pot_cents : 0;
  const newLaughs = prev ? curr.crowd.laugh_events - prev.crowd.laugh_events : curr.crowd.laugh_events;

  if (laughVel >= config.laughSpikePerSec) {
    out.push({
      trigger: 'audience_laugh_spike',
      action: 'iris_widen',
      latency_ms: 0,
      source: 'reflex-v1',
      set_time_ms: curr.set_time_ms,
    });
  }

  // Silence: no new laughs for silenceSec while a set is live.
  // Approximated from sense cadence: prev snapshot had equal laughs and
  // the gap covers the window (exact last-laugh tracking lives in the
  // raw reaction log, not the batched sense).
  if (prev && newLaughs <= 0 && dtSec >= config.silenceSec) {
    out.push({
      trigger: 'dead_silence',
      action: 'stillness',
      latency_ms: 0,
      source: 'reflex-v1',
      text: microLine(curr.seq),
      set_time_ms: curr.set_time_ms,
    });
  }

  if (potDelta >= config.bigTipCents) {
    out.push({
      trigger: 'big_tip',
      action: 'desk_flash',
      latency_ms: 0,
      source: 'reflex-v1',
      text: microLine(curr.seq + 1),
      set_time_ms: curr.set_time_ms,
    });
  }

  if (wtfVel >= config.wtfPerSec) {
    out.push({
      trigger: 'wtf_spike',
      action: 'look_at_chatgpt',
      latency_ms: 0,
      source: 'reflex-v1',
      set_time_ms: curr.set_time_ms,
    });
  }

  if (recentEventTypes.includes('judge.chatgpt.locked') || recentEventTypes.includes('judge.reveal')) {
    out.push({
      trigger: 'chatgpt_score_reveal',
      action: 'look_at_chatgpt',
      latency_ms: 0,
      source: 'reflex-v1',
      set_time_ms: curr.set_time_ms,
    });
  }

  return out;
}
