/**
 * Delivery: the party write-a-minute suggester (role → delivery, pause, hold,
 * emphasis), tuned by the character's physicality (home delivery, pace, how
 * long they hold after a punch). set.set_delivery overrides one line.
 */
import { DELIVERIES, suggestDelivery, type LineDelivery, type PartyIdentity } from '@funnier/party';
import type { CharacterTheory, SetLine } from './types';

export function suggestSetDelivery(lines: SetLine[], t: CharacterTheory): SetLine[] {
  const asIdentity = { persona: { delivery: t.physicality.delivery_default } } as unknown as PartyIdentity;
  const base = suggestDelivery(lines, asIdentity) as SetLine[];
  const hold = t.physicality.punchline_hold_ms;
  const pace = t.physicality.pace || 1;
  const home = t.physicality.delivery_default;
  return base.map((l, i) => {
    const src = lines[i];
    const out: SetLine = { ...src, delivery: l.delivery, pause_ms: Math.round(l.pause_ms / pace), hold_ms: l.hold_ms, emphasis: l.emphasis };
    if (src.role === 'punch') out.hold_ms = hold;
    if (src.role === 'tag') out.hold_ms = Math.round(hold * 0.75);
    if (src.role === 'callback') { out.hold_ms = hold; if (home === 'deadpan') out.delivery = 'deadpan'; }
    if (src.role === 'closer') out.hold_ms = Math.round(hold * 1.25);
    if (src.source === 'segue') out.delivery = home === 'manic' ? 'manic' : 'deliberate';
    return out;
  });
}

export interface DeliveryPatch { line: string; style?: LineDelivery; pause_ms?: number; hold_ms?: number; emphasis?: string[] }

/** set.set_delivery: override one line's style / pause / hold / emphasis. Returns the new lines and a one-line receipt. */
export function setLineDelivery(lines: SetLine[], p: DeliveryPatch): { lines: SetLine[]; receipt: string } {
  const i = lines.findIndex((l) => l.id === p.line);
  if (i < 0) throw new Error(`no line ${p.line} (lines are l1..l${lines.length})`);
  if (p.style && p.style !== 'pause' && !DELIVERIES.includes(p.style)) throw new Error(`style must be one of ${[...DELIVERIES, 'pause'].join(', ')}`);
  const next = lines.map((l, j) => (j === i ? { ...l, delivery: p.style ?? l.delivery, pause_ms: p.pause_ms ?? l.pause_ms, hold_ms: p.hold_ms ?? l.hold_ms, emphasis: p.emphasis ?? l.emphasis } : l));
  const l = next[i];
  return { lines: next, receipt: `${l.id} → ${l.delivery}, pause ${l.pause_ms} ms, hold ${l.hold_ms} ms${l.emphasis.length ? `, hit "${l.emphasis.join(' ')}"` : ''}` };
}
