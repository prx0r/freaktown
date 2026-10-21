/**
 * Demo episodes per set — plain command timelines (control sends them through
 * the transport like any operator action, so the room log replays them).
 */
import type { CastMemberV1 } from '@freaktown/contracts';
import type { DealerSeat } from './poker/PokerDealer';

export interface TimedCommand { at_ms: number; type: string; payload: Record<string, unknown> }

export const NEWS_CAST: CastMemberV1[] = [
  { seat: 'anchor1', character_id: 'pog.dana-deadline', name: 'Dana Deadline', avatar_url: 'basic', kind: 'character' },
  { seat: 'anchor2', character_id: 'pog.the-algorithm', name: 'The Algorithm', avatar_url: 'basic:robot', kind: 'character' },
];

export const NEWS_HEADLINES = [
  { kicker: 'breaking', text: 'Local robot wins pie contest, refuses to eat pie', a: 'Breaking tonight: a local robot has won the county pie contest. It then refused to eat the pie, citing firmware.', b: 'I can confirm the pie was excellent. Structurally.' },
  { kicker: 'weather', text: 'Forecast: 90% chance of puns by Friday', a: 'Weather now. Forecasters say there is a ninety percent chance of puns by Friday.', b: 'I would bring an umbrella. The puns will be dry.' },
  { kicker: 'sport', text: 'Freak Town poker night ends in a five-way tie', a: 'And in sport, the Freak Town poker night ended in a five way tie, which the rules say is impossible.', b: 'The rules have been informed. They are taking it badly.' },
];

export function newsDemo(): TimedCommand[] {
  const out: TimedCommand[] = [
    { at_ms: 0, type: 'set.load', payload: { setId: 'news-studio', title: 'Freak Town News', cast: NEWS_CAST } },
    { at_ms: 600, type: 'overlay.ticker', payload: { items: NEWS_HEADLINES.map((h) => `${h.kicker.toUpperCase()}: ${h.text}`).concat(['Markets: chips up 4%', 'Traffic: the mic stand is blocking lane two']) } },
    { at_ms: 900, type: 'set.auto_director', payload: { on: false } },
    { at_ms: 1000, type: 'set.camera', payload: { cue: 'wide' } },
  ];
  let t = 2200;
  NEWS_HEADLINES.forEach((h, i) => {
    out.push({ at_ms: t, type: 'overlay.headline', payload: { text: h.text, kicker: h.kicker } });
    out.push({ at_ms: t, type: 'set.camera', payload: { cue: i === 1 ? 'screen' : 'anchor1-single' } });
    out.push({ at_ms: t + 100, type: 'overlay.lower_third', payload: { name: 'Dana Deadline', title: h.text, show: true } });
    out.push({ at_ms: t + 200, type: 'dialogue.line', payload: { seat: 'anchor1', text: h.a, emotion: i === 0 ? 'excited' : 'warm' } });
    t += 200 + h.a.split(' ').length * 330 + 500;
    out.push({ at_ms: t, type: 'set.camera', payload: { cue: i === 2 ? 'two-shot' : 'anchor2-single' } });
    out.push({ at_ms: t + 50, type: 'overlay.lower_third', payload: { name: 'The Algorithm', title: 'Co-anchor · probably sentient', show: true } });
    out.push({ at_ms: t + 150, type: 'dialogue.line', payload: { seat: 'anchor2', text: h.b, emotion: 'deadpan' } });
    t += 150 + h.b.split(' ').length * 330 + 700;
  });
  out.push({ at_ms: t, type: 'overlay.lower_third', payload: { name: '', show: false } });
  out.push({ at_ms: t, type: 'set.camera', payload: { cue: 'wide' } });
  return out;
}

export const PODCAST_CAST: CastMemberV1[] = [
  { seat: 'seat1', character_id: 'pog.captain-ata-ashcroft', name: 'Captain Ata', avatar_url: 'basic', kind: 'character' },
  { seat: 'seat2', character_id: 'pog.chairman-meow', name: 'Chairman Meow', avatar_url: 'basic', kind: 'character' },
  { seat: 'seat3', character_id: 'pog.the-algorithm', name: 'The Algorithm', avatar_url: 'basic:robot', kind: 'character' },
  { seat: 'seat4', character_id: 'pog.buddha-ultimate-deadpan', name: 'Buddha', avatar_url: 'basic', kind: 'character' },
];

export const PODCAST_LINES: Array<[string, string, string?]> = [
  ['seat1', 'Welcome back to Freak Talk. Today: is a hot dog a sandwich?', 'excited'],
  ['seat2', 'It is not. A sandwich has dignity.', 'smug'],
  ['seat3', 'I have run the numbers. A hot dog is a taco wearing a tie.', 'deadpan'],
  ['seat1', 'A taco wearing a tie.', 'surprised'],
  ['seat2', 'Absolutely not.', 'annoyed'],
  ['seat3', 'Statistically, yes.', 'deadpan'],
  ['seat1', 'Okay. Next question. Should robots pay rent?', 'playful'],
  ['seat3', 'I live in the cloud. The cloud is very expensive.', 'sad'],
  ['seat2', 'I knock things off the cloud. For free.', 'smug'],
  ['seat4', 'I once meditated for forty-nine days. The Wi-Fi never came back.', 'deadpan'],
  ['seat2', 'That explains the buffering.', 'smug'],
];

export function podcastDemo(): TimedCommand[] {
  const out: TimedCommand[] = [
    { at_ms: 0, type: 'set.load', payload: { setId: 'podcast', title: 'Freak Talk', cast: PODCAST_CAST } },
    { at_ms: 500, type: 'set.auto_director', payload: { on: true } },
  ];
  let t = 1800;
  PODCAST_LINES.forEach(([seat, text, emotion]) => {
    out.push({ at_ms: t, type: 'dialogue.line', payload: { seat, text, ...(emotion ? { emotion } : {}) } });
    t += Math.max(900, text.split(' ').length * 330 + 300) + 150;
  });
  return out;
}

export const POKER_CAST: CastMemberV1[] = [
  { seat: 'seat0', character_id: 'pog.captain-ata-ashcroft', name: 'Captain Ata', avatar_url: 'basic', kind: 'bot' },
  { seat: 'seat1', character_id: 'pog.buddha-ultimate-deadpan', name: 'Buddha', avatar_url: 'basic', kind: 'bot' },
  { seat: 'seat2', character_id: 'pog.chairman-meow', name: 'Chairman Meow', avatar_url: 'basic', kind: 'bot' },
  { seat: 'seat3', character_id: 'pog.the-algorithm', name: 'The Algorithm', avatar_url: 'basic:robot', kind: 'bot' },
  { seat: 'seat6', character_id: 'pog.dana-deadline', name: 'Dana Deadline', avatar_url: 'basic', kind: 'bot' },
];
/** The open seat a human can take from /play/:ep/seat/4. */
export const POKER_HUMAN_SEAT = 4;

export function pokerSeats(humanName = 'You'): DealerSeat[] {
  return [
    { seat: 0, name: 'Captain Ata', stack: 1000, kind: 'bot', style: 'loose' },
    { seat: 1, name: 'Buddha', stack: 1000, kind: 'bot', style: 'tight' },
    { seat: 2, name: 'Chairman Meow', stack: 1000, kind: 'bot', style: 'calling-station' },
    { seat: 3, name: 'The Algorithm', stack: 1000, kind: 'bot', style: 'tight' },
    { seat: POKER_HUMAN_SEAT, name: humanName, stack: 1000, kind: 'human' },
    { seat: 6, name: 'Dana Deadline', stack: 1000, kind: 'bot', style: 'calling-station' },
  ];
}

export function pokerDemoIntro(): TimedCommand[] {
  return [
    { at_ms: 0, type: 'set.load', payload: { setId: 'poker-table', title: 'Freak Town Poker', cast: POKER_CAST } },
    { at_ms: 400, type: 'set.camera', payload: { cue: 'orbit' } },
  ];
}
