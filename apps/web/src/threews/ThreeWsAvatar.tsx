/**
 * ThreeWsAvatar — killella's three.ws actor primitive.
 *
 * Division of labor (honest about the public API):
 * - `<agent-3d>` owns: scene, avatar GLB, idle/clip animation, gestures
 *   (play/wave), gaze (lookAt), load lifecycle events.
 * - Killella owns: pre-generated set audio (exact timing), captions,
 *   cameras, cues, show state.
 *
 * Live dialogue lines (Ella roasts, judge remarks — timing not
 * frame-critical) go through el.say(). The 60s sets play through our
 * audio element so pauses stay exact; the avatar idles + gestures.
 *
 * Failure contract: poster + status + fallback link. Never a black box.
 */

import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { DEFAULT_AVATAR_URL, ensureAgent3D, type Agent3DLoadError } from './loader';

export interface Agent3DElement extends HTMLElement {
  say(text: string): Promise<unknown>;
  ask(text: string): Promise<unknown>;
  wave(opts?: unknown): Promise<unknown>;
  lookAt(target: string): Promise<unknown>;
  play(clip: string): Promise<unknown>;
  pause(): void;
  resume(): void;
  destroy(): void;
}

export type AvatarStatus =
  | { state: 'loading'; progress: string }
  | { state: 'ready' }
  | { state: 'speaking' }
  | { state: 'error'; message: string };

export interface ThreeWsAvatarHandle {
  say(text: string): Promise<void>;
  playClip(clip: string): Promise<void>;
  wave(): Promise<void>;
  lookAtUser(): Promise<void>;
  readonly ready: boolean;
}

interface Props {
  avatarUrl?: string;
  performerName?: string;
  onStatus?: (status: AvatarStatus) => void;
  fallbackHref?: string;
}

function errorMessage(err: Agent3DLoadError): string {
  if (err.kind === 'timeout') return 'three.ws runtime timed out (15s). Check network.';
  return err.message;
}

export const ThreeWsAvatar = forwardRef<ThreeWsAvatarHandle, Props>(function ThreeWsAvatar(
  { avatarUrl = DEFAULT_AVATAR_URL, performerName = 'Guest Freak', onStatus, fallbackHref = '/stage/demo' },
  ref
) {
  const hostRef = useRef<HTMLDivElement>(null);
  const elRef = useRef<Agent3DElement | null>(null);
  const [status, setStatus] = useState<AvatarStatus>({ state: 'loading', progress: 'loading three.ws runtime…' });
  const [loadPct, setLoadPct] = useState<string>('');

  const emit = (s: AvatarStatus) => {
    setStatus(s);
    onStatus?.(s);
  };

  useImperativeHandle(ref, () => ({
    get ready() {
      return status.state === 'ready' || status.state === 'speaking';
    },
    async say(text: string) {
      if (!elRef.current) throw new Error('avatar not ready');
      await elRef.current.say(text);
    },
    async playClip(clip: string) {
      if (!elRef.current) throw new Error('avatar not ready');
      try {
        await elRef.current.play(clip);
      } catch {
        // Unknown clips must never break the show; idle continues.
      }
    },
    async wave() {
      if (!elRef.current) throw new Error('avatar not ready');
      await elRef.current.wave({ style: 'enthusiastic' });
    },
    async lookAtUser() {
      if (!elRef.current) throw new Error('avatar not ready');
      await elRef.current.lookAt('user');
    },
  }), [status.state]);

  useEffect(() => {
    let cancelled = false;
    const host = hostRef.current;
    if (!host) return;

    emit({ state: 'loading', progress: 'loading three.ws runtime…' });

    ensureAgent3D()
      .then(() => {
        if (cancelled) return;
        host.innerHTML = '';
        const el = document.createElement('agent-3d') as unknown as Agent3DElement;
        el.setAttribute('body', avatarUrl);
        el.setAttribute('mode', 'inline');
        el.setAttribute('kiosk', '');
        el.setAttribute('eager', '');
        el.setAttribute('clip', 'idle');
        el.style.width = '100%';
        el.style.height = '100%';
        el.style.display = 'block';

        // Slot fallback content (rendered if the element errors internally).
        const fallback = document.createElement('span');
        fallback.setAttribute('slot', 'error');
        fallback.style.cssText = 'color:#888;font-size:13px;';
        fallback.textContent = '3D performer unavailable — audio continues.';
        el.appendChild(fallback);

        el.addEventListener('agent:ready', () => {
          if (!cancelled) emit({ state: 'ready' });
        });
        el.addEventListener('agent:load-progress', (ev) => {
          if (cancelled) return;
          const detail = (ev as CustomEvent).detail as { phase?: string; pct?: number } | undefined;
          const pct = typeof detail?.pct === 'number' ? ` ${Math.round(detail.pct * 100)}%` : '';
          setLoadPct(`${detail?.phase ?? 'loading'}${pct}`);
        });
        el.addEventListener('agent:error', (ev) => {
          if (cancelled) return;
          const detail = (ev as CustomEvent).detail as { phase?: string; error?: unknown } | undefined;
          const msg = typeof detail?.error === 'string' ? detail.error : JSON.stringify(detail?.error ?? 'unknown');
          emit({ state: 'error', message: `avatar error [${detail?.phase ?? '?'}]: ${msg}` });
        });
        el.addEventListener('voice:speech-start', () => {
          if (!cancelled) emit({ state: 'speaking' });
        });
        el.addEventListener('voice:speech-end', () => {
          if (!cancelled) emit({ state: 'ready' });
        });

        host.appendChild(el);
        elRef.current = el;
      })
      .catch((err: Agent3DLoadError) => {
        if (!cancelled) emit({ state: 'error', message: errorMessage(err) });
      });

    return () => {
      cancelled = true;
      try {
        elRef.current?.destroy();
      } catch {
        // destroy is best-effort on unmount
      }
      elRef.current = null;
      if (host) host.innerHTML = '';
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [avatarUrl]);

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div ref={hostRef} style={{ width: '100%', height: '100%' }} />

      {/* Poster / status overlay — the anti-black-screen layer */}
      {status.state !== 'ready' && status.state !== 'speaking' && (
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 8,
          background: 'radial-gradient(circle at 50% 0, #1a1020 0, #09090b 60%)',
          color: '#e0e0e0', textAlign: 'center', padding: 20,
        }}>
          <div style={{ fontSize: 44 }}>🎤</div>
          <div style={{ fontSize: 16, fontWeight: 'bold', color: '#ff00aa' }}>{performerName}</div>
          {status.state === 'loading' && (
            <div style={{ fontSize: 12, color: '#888' }}>
              {status.progress} {loadPct}
            </div>
          )}
          {status.state === 'error' && (
            <>
              <div style={{ fontSize: 12, color: '#ff6666', maxWidth: 320 }}>{status.message}</div>
              <a href={fallbackHref} style={{ fontSize: 12, color: '#00d4ff' }}>
                Open VRM stage instead →
              </a>
            </>
          )}
        </div>
      )}

      {status.state === 'speaking' && (
        <div style={{
          position: 'absolute', bottom: 12, left: '50%', transform: 'translateX(-50%)',
          fontSize: 11, color: '#ff00aa', background: 'rgba(0,0,0,0.6)',
          padding: '4px 10px', borderRadius: 4,
        }}>
          ● speaking
        </div>
      )}
    </div>
  );
});
