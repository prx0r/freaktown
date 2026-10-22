/** Set registry: the catalogue of SetDefinitions the stage/control can load. */
import type { SetDefinition, SeatAnchor } from './types';
import { COMEDY_CLUB, NEWS_STUDIO, PODCAST, POKER_TABLE } from './definitions';

export class SetRegistry {
  private sets = new Map<string, SetDefinition>();

  register(def: SetDefinition): this {
    validateSetDefinition(def);
    this.sets.set(def.id, def);
    return this;
  }
  get(id: string): SetDefinition | undefined { return this.sets.get(id); }
  require(id: string): SetDefinition {
    const d = this.sets.get(id);
    if (!d) throw new Error(`unknown set "${id}" (have: ${[...this.sets.keys()].join(', ')})`);
    return d;
  }
  has(id: string): boolean { return this.sets.has(id); }
  list(): SetDefinition[] { return [...this.sets.values()]; }
}

export function validateSetDefinition(def: SetDefinition): void {
  if (!def.id || !/^[a-z0-9-]+$/.test(def.id)) throw new Error(`bad set id "${def.id}"`);
  if (!def.seats.length) throw new Error(`set ${def.id}: needs at least one seat`);
  const ids = new Set<string>();
  for (const s of def.seats) {
    if (ids.has(s.id)) throw new Error(`set ${def.id}: duplicate seat "${s.id}"`);
    ids.add(s.id);
  }
  for (const [name, cam] of Object.entries(def.cameras)) {
    if (cam.seat && !findSeat(def, cam.seat)) throw new Error(`set ${def.id}: camera ${name} bound to unknown seat "${cam.seat}"`);
  }
  if (!def.cameras[def.defaultCamera] && def.defaultCamera !== 'wide') throw new Error(`set ${def.id}: defaultCamera "${def.defaultCamera}" missing`);
}

/** Seat lookup by id, then role (first match), then numeric index ("2" or "seat2" style). */
export function findSeat(def: Pick<SetDefinition, 'seats'> & { marks?: SeatAnchor[] }, ref: string): SeatAnchor | undefined {
  const r = ref.trim();
  const byId = def.seats.find((s) => s.id === r);
  if (byId) return byId;
  const byRole = def.seats.find((s) => s.role === r);
  if (byRole) return byRole;
  if (/^\d+$/.test(r)) return def.seats[Number(r)];
  return def.marks?.find((m) => m.id === r);
}

/** The built-in sets. Comedy club stays set #1 (classic StageRuntime renders it). */
export const SET_REGISTRY = new SetRegistry()
  .register(COMEDY_CLUB)
  .register(NEWS_STUDIO)
  .register(PODCAST)
  .register(POKER_TABLE);
