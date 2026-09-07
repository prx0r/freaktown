/**
 * Privy access-token verification (real JWT verification, not decoding).
 *
 * Privy signs access tokens (RS256). We verify signature via their JWKS,
 * plus issuer (privy.io), audience (our app ID) and expiry — via jose.
 * A forged payload with a valid shape fails here. This gates /command
 * and /stage-token (with requireAdmin), so it is Episode-Zero-blocking.
 *
 * The JWKS fetcher is injectable so tests can serve a local JWKS with a
 * generated keypair instead of hitting auth.privy.io.
 */

import { createRemoteJWKSet, jwtVerify, type JWTPayload } from 'jose';

export interface PrivyClaims extends JWTPayload {
  sub: string; // did:privy:... — stable user id, used as privy_user_id
  email?: string;
}

export interface VerifyOptions {
  appId: string;
  /** Override for tests / self-hosted JWKS. Defaults to Privy's endpoint. */
  jwksUrl?: string;
}

const jwksCache = new Map<string, ReturnType<typeof createRemoteJWKSet>>();

function jwksFor(appId: string, jwksUrl?: string) {
  const url = jwksUrl ?? `https://auth.privy.io/api/v1/apps/${appId}/jwks.json`;
  let set = jwksCache.get(url);
  if (!set) {
    set = createRemoteJWKSet(new URL(url));
    jwksCache.set(url, set);
  }
  return set;
}

export function clearJwksCache(): void {
  jwksCache.clear();
}

export async function verifyPrivyAccessToken(
  token: string,
  opts: VerifyOptions
): Promise<PrivyClaims> {
  if (!token || typeof token !== 'string') {
    throw new Error('missing token');
  }
  if (!opts.appId) {
    throw new Error('Privy app ID not configured');
  }
  const { payload } = await jwtVerify(token, jwksFor(opts.appId, opts.jwksUrl), {
    issuer: 'privy.io',
    audience: opts.appId,
  });
  if (typeof payload.sub !== 'string' || !payload.sub) {
    throw new Error('token has no sub');
  }
  return payload as PrivyClaims;
}
