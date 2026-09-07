/**
 * three.ws loader — pinned runtime with integrity + timeout.
 *
 * Pin matches freaktown's Black Room editor (agent-3d 1.5.2). Never float
 * `latest` on a production stage: three.ws's own docs recommend pinning.
 * Never a black screen: failure resolves to a typed error the UI renders
 * as poster + fallback, never an empty canvas.
 */

export const AGENT_3D_URL = 'https://three.ws/agent-3d/1.5.2/agent-3d.js';
export const AGENT_3D_INTEGRITY =
  'sha384-xkFDjVP866hYt7voUhfnQHj6IO4hYxA6n8Laupk+VtD6y+IKiO/AZdE3VbfLtg0C';

export const DEFAULT_AVATAR_URL = 'https://three.ws/avatars/michelle.glb';

export type Agent3DLoadError =
  | { kind: 'timeout' }
  | { kind: 'integrity'; message: string }
  | { kind: 'network'; message: string };

let loadPromise: Promise<void> | null = null;

export function ensureAgent3D(timeoutMs = 15000): Promise<void> {
  if (typeof customElements !== 'undefined' && customElements.get('agent-3d')) {
    return Promise.resolve();
  }
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.type = 'module';
    script.src = AGENT_3D_URL;
    script.integrity = AGENT_3D_INTEGRITY;
    script.crossOrigin = 'anonymous';

    const timer = window.setTimeout(() => {
      script.remove();
      loadPromise = null;
      const err: Agent3DLoadError = { kind: 'timeout' };
      reject(err);
    }, timeoutMs);

    script.onload = () => {
      window.clearTimeout(timer);
      // The module registers the custom element asynchronously; poll briefly.
      const started = Date.now();
      const check = () => {
        if (customElements.get('agent-3d')) {
          resolve();
        } else if (Date.now() - started > 5000) {
          loadPromise = null;
          const err: Agent3DLoadError = {
            kind: 'network',
            message: 'agent-3d element never registered',
          };
          reject(err);
        } else {
          window.setTimeout(check, 100);
        }
      };
      check();
    };

    script.onerror = () => {
      window.clearTimeout(timer);
      loadPromise = null;
      const err: Agent3DLoadError = {
        kind: 'integrity',
        message: 'three.ws runtime failed to load (network or SRI mismatch)',
      };
      reject(err);
    };

    document.head.appendChild(script);
  });

  return loadPromise;
}
