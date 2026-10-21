/**
 * Transport selection for apps/live. One interface, two links:
 *   ?transport=local  BroadcastChannel + localStorage (default; no Cloudflare)
 *   ?transport=room   EpisodeRoom DO (wrangler dev / production worker)
 * Override the default with VITE_LIVE_TRANSPORT=room at build time.
 */

import { EpisodeRoomTransport, LocalTransport, type LiveTransport } from '@freaktown/stage-runtime';

export type TransportMode = 'local' | 'room';

const ADMIN_KEY_STORAGE = 'freaktown_admin_key';

export function transportMode(search: URLSearchParams): TransportMode {
  const q = search.get('transport');
  if (q === 'room' || q === 'local') return q;
  return (import.meta.env.VITE_LIVE_TRANSPORT as TransportMode | undefined) === 'room' ? 'room' : 'local';
}

export function adminKey(): string {
  try { return localStorage.getItem(ADMIN_KEY_STORAGE) ?? ''; } catch { return ''; }
}

export function setAdminKey(key: string): void {
  try { localStorage.setItem(ADMIN_KEY_STORAGE, key); } catch { /* ignore */ }
}

export function createTransport(mode: TransportMode, opts: { authKey?: string } = {}): LiveTransport {
  if (mode === 'room') {
    return new EpisodeRoomTransport({
      baseUrl: (import.meta.env.VITE_LIVE_ROOM_ORIGIN as string | undefined) || undefined,
      pathPrefix: (import.meta.env.VITE_LIVE_ROOM_PREFIX as string | undefined) || undefined,
      authKey: opts.authKey,
    });
  }
  return new LocalTransport();
}

/** Resolve a relative asset path from an event against the app base. */
export function resolveAsset(url: string): string {
  if (/^(https?:|blob:|data:)/.test(url) || url.startsWith('/')) return url;
  return new URL(url, `${window.location.origin}${import.meta.env.BASE_URL}`).toString();
}

export interface SetEntry {
  id: string;
  title: string;
  character_name: string;
  character_id: string;
  premise: string;
  set_url: string;
  audio_url: string;
  avatar_url: string;
  avatar_note: string;
  beats: number;
  duration_ms: number;
  source: string;
}

export async function loadSetCatalog(): Promise<SetEntry[]> {
  const res = await fetch(resolveAsset('sets/index.json'));
  if (!res.ok) throw new Error(`sets/index.json ${res.status}`);
  const data = (await res.json()) as { sets: SetEntry[] };
  return data.sets;
}
