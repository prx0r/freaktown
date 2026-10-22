/**
 * Agent players: a persistent identity + its taste model + joke sources.
 * planTurn() turns a joke into timed stage lines (in the identity's delivery);
 * react() decides — honestly, from taste — whether the agent cracks.
 */
import { nextJoke, DeckJokeSource, TemplateJokeSource, type Delivery, type Joke, type JokeSource, type Mechanism } from './jokes';
import type { PartyIdentity } from './identity';
import { reactToJoke, type SmileCurve } from './taste';
import type { Rng } from './rng';

export interface PlannedLine { t: number; text: string; duration_ms: number; delivery: Delivery; role: 'setup' | 'punch' | 'tag' }
export interface TurnPlan { joke: Joke; lines: PlannedLine[]; punchEndsAt: number; endsAt: number }

const PACE: Record<Delivery, number> = { deadpan: 1.1, deliberate: 1.25, manic: 0.8, warm: 1.0, conspiratorial: 1.05 };
export const EMOTION_FOR: Record<Delivery, string> = { deadpan: 'neutral', deliberate: 'relaxed', manic: 'surprised', warm: 'happy', conspiratorial: 'relaxed' };

export function lineMs(text: string, delivery: Delivery = 'warm'): number {
  const words = text.split(/\s+/).filter(Boolean).length;
  return Math.round((words * 330 + 350) * PACE[delivery]);
}

export class AgentPlayer {
  readonly seen: Mechanism[] = [];
  constructor(readonly identity: PartyIdentity, private sources: JokeSource[] = [new DeckJokeSource(), new TemplateJokeSource()]) {}

  get id(): string { return this.identity.id; }

  planTurn(t0: number, rng: Rng, used: Set<string>): TurnPlan {
    const joke = nextJoke(this.sources, { rng, used, prefer: this.identity.persona.writes, performerId: this.id });
    const d = this.identity.persona.delivery;
    const lines: PlannedLine[] = [];
    let t = t0 + 600;
    let punchEndsAt = t;
    for (const l of joke.lines) {
      const delivery = l.delivery ?? d;
      if (l.role === 'punch') t += Math.round((l.pause_ms ?? 400) * (d === 'deadpan' || d === 'deliberate' ? 1.4 : 1));
      const duration_ms = lineMs(l.text, delivery);
      lines.push({ t, text: l.text, duration_ms, delivery, role: l.role });
      t += duration_ms + 150;
      if (l.role === 'punch') punchEndsAt = t - 150;
    }
    if (this.identity.persona.catchphrase && rng() < 0.35) {
      t += 700;
      const text = this.identity.persona.catchphrase;
      const duration_ms = lineMs(text, d);
      lines.push({ t, text, duration_ms, delivery: d, role: 'tag' });
      t += duration_ms;
    }
    return { joke, lines, punchEndsAt, endsAt: t + 1800 };
  }

  react(joke: Joke, rng: Rng): SmileCurve {
    const c = reactToJoke(this.identity.taste, joke, rng, this.seen);
    this.seen.push(...joke.tags);
    return c;
  }
}

/** A human's bit, as the agents hear it (no transcript needed: rated as an average-quality observational bit). */
export function humanJoke(n: number, text?: string): Joke {
  return { id: `human-${n}`, tags: ['observational', 'self-deprecating'], quality: 0.55, source: 'deck:original', lines: [{ text: text || '(the human tells a joke)', role: 'punch' }] };
}
