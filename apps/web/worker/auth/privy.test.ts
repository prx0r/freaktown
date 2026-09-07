/**
 * Privy JWT verification — offline tests with a local JWKS server.
 *
 * A forged payload with valid shape must fail. Only tokens signed by
 * the JWKS key, with correct issuer/audience and live expiry, pass.
 */
import { createServer, type Server } from 'node:http';
import { generateKeyPairSync, type KeyObject } from 'node:crypto';
import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { SignJWT, exportJWK, importPKCS8, generateKeyPair, type JWTPayload } from 'jose';
import { verifyPrivyAccessToken, clearJwksCache } from './privy';

const APP_ID = 'test-app';

let privateKey: KeyObject;
let jwksUrl = '';
let server: Server;

async function sign(claims: JWTPayload, key?: KeyObject): Promise<string> {
  const signer = key ?? privateKey;
  const { default: ignore } = { default: null };
  void ignore;
  const joseKey = signer as unknown as Parameters<SignJWT['sign']>[0];
  return new SignJWT(claims)
    .setProtectedHeader({ alg: 'RS256', kid: 'test-key' })
    .sign(joseKey);
}

beforeAll(async () => {
  clearJwksCache();
  const { publicKey, privateKey: priv } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  privateKey = priv;

  const pubJwk = await exportJWK(publicKey);
  const jwks = { keys: [{ ...pubJwk, kid: 'test-key', use: 'sig', alg: 'RS256' }] };

  server = createServer((_req, res) => {
    res.writeHead(200, { 'content-type': 'application/json' });
    res.end(JSON.stringify(jwks));
  });
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const addr = server.address();
  const port = typeof addr === 'object' && addr ? addr.port : 0;
  jwksUrl = `http://127.0.0.1:${port}/jwks.json`;
});

afterAll(async () => {
  await new Promise<void>((resolve) => server.close(() => resolve()));
  clearJwksCache();
});

function baseClaims() {
  const now = Math.floor(Date.now() / 1000);
  return {
    iss: 'privy.io',
    aud: APP_ID,
    sub: 'did:privy:abc123',
    iat: now,
    exp: now + 300,
  };
}

describe('verifyPrivyAccessToken', () => {
  it('accepts a valid token', async () => {
    const token = await sign(baseClaims());
    const claims = await verifyPrivyAccessToken(token, { appId: APP_ID, jwksUrl });
    expect(claims.sub).toBe('did:privy:abc123');
  });

  it('rejects a forged payload (valid shape, attacker key)', async () => {
    const { generateKeyPair, SignJWT: SJ } = await import('jose');
    const evil = await generateKeyPair('RS256');
    const token = await new SJ(baseClaims())
      .setProtectedHeader({ alg: 'RS256', kid: 'evil' })
      .sign(evil.privateKey);
    await expect(verifyPrivyAccessToken(token, { appId: APP_ID, jwksUrl })).rejects.toThrow();
  });

  it('rejects wrong audience', async () => {
    const token = await sign({ ...baseClaims(), aud: 'other-app' });
    await expect(verifyPrivyAccessToken(token, { appId: APP_ID, jwksUrl })).rejects.toThrow();
  });

  it('rejects wrong issuer', async () => {
    const token = await sign({ ...baseClaims(), iss: 'evil.io' });
    await expect(verifyPrivyAccessToken(token, { appId: APP_ID, jwksUrl })).rejects.toThrow();
  });

  it('rejects expired tokens', async () => {
    const now = Math.floor(Date.now() / 1000);
    const token = await sign({ ...baseClaims(), exp: now - 10 });
    await expect(verifyPrivyAccessToken(token, { appId: APP_ID, jwksUrl })).rejects.toThrow();
  });

  it('rejects garbage', async () => {
    await expect(
      verifyPrivyAccessToken('not.a.jwt', { appId: APP_ID, jwksUrl })
    ).rejects.toThrow();
  });

  it('rejects missing token / app id', async () => {
    await expect(verifyPrivyAccessToken('', { appId: APP_ID, jwksUrl })).rejects.toThrow();
    const token = await sign(baseClaims());
    await expect(verifyPrivyAccessToken(token, { appId: '', jwksUrl })).rejects.toThrow();
  });
});
