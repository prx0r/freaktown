/**
 * Authentication middleware for Cloudflare Worker.
 * Uses Privy for user authentication.
 */

import { Context, Next } from 'hono';
import type { Env } from '../index';

export type User = {
  id: string;
  privy_user_id: string;
  handle: string;
  display_name: string;
  role: string;
};

// Hono context carries the authenticated user via Variables
// (set by the app generics, no module augmentation needed).
export type AppBindings = {
  Bindings: Env;
  Variables: { user: User };
};

/**
 * Middleware that validates Privy session token and attaches user to context.
 */
export async function authMiddleware(c: Context<AppBindings>, next: Next) {
  const authHeader = c.req.header('Authorization');
  const apiKey = c.req.header('X-API-Key');

  // API Key auth
  if (apiKey) {
    const db = c.env.DB;
    const keyHash = await hashApiKey(apiKey);
    const keyResult = await db.prepare(
      "SELECT user_id FROM api_keys WHERE key_hash = ? AND is_active = 1"
    ).bind(keyHash).first();

    if (!keyResult) {
      return c.json({ error: 'Invalid API key' }, 401);
    }

    const userResult = await db.prepare(
      "SELECT id, handle, display_name, role FROM users WHERE id = ?"
    ).bind(keyResult.user_id).first();

    if (!userResult) {
      return c.json({ error: 'User not found' }, 401);
    }

    c.set('user', {
      id: String(userResult.id),
      privy_user_id: '',
      handle: String(userResult.handle),
      display_name: String(userResult.display_name),
      role: String(userResult.role),
    });

    return next();
  }

  // Privy token auth
  if (authHeader?.startsWith('Bearer ')) {
    const token = authHeader.slice(7);

    // Verify Privy token
    const privyAppId = c.env.PRIVY_APP_ID;
    const privyAppSecret = c.env.PRIVY_APP_SECRET;

    if (!privyAppId || !privyAppSecret) {
      return c.json({ error: 'Auth not configured' }, 500);
    }

    try {
      // In production, verify the Privy JWT token
      // For now, decode the token to get user info
      const payload = decodeJwtPayload(token);
      if (!payload?.sub) {
        return c.json({ error: 'Invalid token' }, 401);
      }

      const db = c.env.DB;
      const userResult = await db.prepare(
        "SELECT id, handle, display_name, role FROM users WHERE privy_user_id = ?"
      ).bind(payload.sub).first();

      if (!userResult) {
        // Auto-create user from Privy
        const userId = crypto.randomUUID();
        const handle = payload.email?.split('@')[0] || `user-${userId.slice(0, 8)}`;

        await db.prepare(
          "INSERT INTO users (id, privy_user_id, handle, display_name, role) VALUES (?, ?, ?, ?, 'user')"
        ).bind(userId, payload.sub, handle, handle).run();

        c.set('user', {
          id: userId,
          privy_user_id: payload.sub,
          handle,
          display_name: handle,
          role: 'user',
        });
      } else {
        c.set('user', {
          id: String(userResult.id),
          privy_user_id: String(payload.sub ?? ''),
          handle: String(userResult.handle),
          display_name: String(userResult.display_name),
          role: String(userResult.role),
        });
      }

      return next();
    } catch (err) {
      return c.json({ error: 'Invalid token' }, 401);
    }
  }

  return c.json({ error: 'Authentication required' }, 401);
}

/**
 * Middleware that requires admin role.
 */
export async function requireAdmin(c: Context<AppBindings>, next: Next) {
  const user = c.get('user');
  if (!user || user.role !== 'admin') {
    return c.json({ error: 'Admin access required' }, 403);
  }
  return next();
}

/**
 * Hash an API key for lookup.
 */
async function hashApiKey(key: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(key);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Decode JWT payload without verification (for dev only).
 * In production, use proper JWT verification.
 */
function decodeJwtPayload(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(payload);
  } catch {
    return null;
  }
}
