/**
 * Postgres access from Workers via Hyperdrive.
 *
 * Canonical rule: Postgres is durable truth (users, shows, characters,
 * results). D1 holds only edge-local ephemeral data. Nothing new that
 * must survive goes in D1.
 *
 * Provisioning (dashboard/CLI, one time):
 *   wrangler hyperdrive create freak-town-postgres \
 *     --connection-string="postgres://USER:PASS@HOST:5432/DB"
 * then put the returned id in wrangler.jsonc hyperdrive[0].id.
 *
 * Until the binding is provisioned, postgres() returns null and callers
 * must take their legacy path. No silent fallback to D1 for business
 * rows — fail loudly instead.
 */

import type { Env } from '../index';

export interface PostgresHandle {
  connectionString: string;
}

export function postgres(env: Env): PostgresHandle | null {
  const binding = (env as Record<string, unknown>).HYPERDRIVE as
    | { connectionString?: string }
    | undefined;
  const connectionString = binding?.connectionString;
  if (!connectionString) return null;
  return { connectionString };
}
