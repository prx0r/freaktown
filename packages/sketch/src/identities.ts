/**
 * Identities — the sketch layer's bridge to the repo's persistent character
 * identity system (no parallel registry):
 *
 *   assets/character-meshes/cast/cast-index.json   39 `pog.*` identities (name, mesh family, comic engine)
 *   assets/character-meshes/cast/lifecycle.json    voice per identity
 *   assets/character-meshes/cast/motion-*.json     pog.motion-style.v1 (temperament, reaction_delay_ms …)
 *
 * snapshotted by scripts/build-identities.mjs into identities.generated.json
 * (a drift test keeps it in sync). A sketch cast entry names an identity id;
 * the resolver fills name / timing traits from the registry and produces the
 * stage's CastMemberV1 (`set.cast` wire type, same as newsroom + live sets).
 * Unknown ids are allowed (guests, humans): they need an inline name.
 */
import type { CastMemberV1 } from '@funnier/contracts';
import snapshot from './identities.generated.json';
import type { CastEntry, SketchScriptV1, SketchTiming } from './schema';

export interface IdentityMotion {
  family: string | null;
  energy: number | null;
  confidence: number | null;
  nervousness: number | null;
  theatricality: number | null;
  reaction_delay_ms: number | null;
  gesture_frequency: string | null;
  signature_action: string | null;
}

export interface Identity {
  id: string;
  name: string;
  family: string;
  mesh: string;
  engine: string;
  voice: string | null;
  motion: IdentityMotion | null;
}

const BY_ID = new Map<string, Identity>((snapshot.identities as Identity[]).map((i) => [i.id, i]));

export function listIdentities(): Identity[] { return [...BY_ID.values()]; }
export function getIdentity(id: string): Identity | undefined { return BY_ID.get(id); }

/** A cast member resolved against the registry, with the traits the sketch timing reads. */
export interface ResolvedCast {
  role: string;
  seat: string;
  identity: string;
  registered: boolean;
  name: string;
  avatar_url: string;
  /** Reaction latency (ms): identity motion-style, else the script default. */
  react_delay_ms: number;
  /** 0..1 energy (scales reaction / gesture intensity). */
  energy: number;
  /** Idle-glance multiplier: nervous characters glance more, confident ones hold. */
  restlessness: number;
  voice: string | null;
}

/** Robots and pixel folk get the robot BASIC body by default; everyone else the BASIC human. */
function defaultAvatar(id: Identity | undefined): string {
  return id && (id.family === 'robot' || id.family === 'pixellabs') ? 'basic:robot' : 'basic';
}

export function resolveCastEntry(c: CastEntry, timing: SketchTiming): ResolvedCast {
  const id = getIdentity(c.identity);
  if (!id && !c.name) throw new Error(`cast ${c.role}: identity "${c.identity}" is not in the registry; give it a name`);
  const m = id?.motion;
  const nerv = m?.nervousness ?? 0.4, conf = m?.confidence ?? 0.5;
  return {
    role: c.role,
    seat: c.seat,
    identity: c.identity,
    registered: !!id,
    name: c.name ?? id!.name,
    avatar_url: c.avatar_url ?? defaultAvatar(id),
    react_delay_ms: m?.reaction_delay_ms ?? timing.react_delay_ms,
    energy: m?.energy ?? 0.6,
    restlessness: Math.max(0.3, Math.min(1.8, 1 + (nerv - 0.4) * 1.5 - (conf - 0.5) * 0.8)),
    voice: id?.voice ?? null,
  };
}

export function resolveCast(s: Pick<SketchScriptV1, 'cast'>, timing: SketchTiming): ResolvedCast[] {
  return s.cast.map((c) => resolveCastEntry(c, timing));
}

/** set.cast payload (wire type shared with live sets + newsroom). */
export function toCastMembers(cast: ResolvedCast[]): CastMemberV1[] {
  return cast.map((c) => ({ seat: c.seat, character_id: c.identity, name: c.name, avatar_url: c.avatar_url, kind: 'character' as const }));
}
