/**
 * Optional Mutuals Character Harness extension -> FUNNIER Party stage.
 * Apache-2.0 compatible; only public performed lines and the acting cues are
 * transmitted. NEVER send session history, user mic, credentials or memory.
 *
 * Must run after the upstream `director` extension to see its beats.
 * Handler is non-blocking: failures are logged and do not delay TTS.
 */
type Beat = { span?: unknown; emotion?: unknown; gesture?: unknown; camera?: unknown; register?: unknown };
type State = {
  sentence?: string;
  beats?: Beat[];
  character?: { id?: string; name?: string };
};
type Input = { event: string; state: State };

const safe = (v: unknown, limit: number) =>
  (typeof v === 'string' ? v : '').replace(/[\u0000-\u001f\u007f]/g, ' ').slice(0, limit);

export default async function ({ event, state }: Input) {
  if (event !== 'on_sentence' || !state?.sentence) return;
  const endpoint = process.env.FUNNIER_PARTY_ENDPOINT;
  const token = process.env.FUNNIER_HOST_TOKEN;
  if (!endpoint || !token) return;
  // The endpoint is operator-controlled, NOT supplied in conversation text.
  const beats = Array.isArray(state.beats) ? state.beats.slice(0, 16) : [];
  const body = {
    host_token: token,
    actor: safe(state.character?.name || state.character?.id || 'Guest Freak', 48),
    text: safe(state.sentence, 400),
    beats: beats.map(b => ({
      span: safe(b.span, 120), emotion: safe(b.emotion, 24),
      gesture: safe(b.gesture, 24), camera: safe(b.camera, 24),
      register: safe(b.register, 24),
    })),
  };
  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(2000),
    });
    if (!response.ok) console.warn(`[funnier-party] relay HTTP ${response.status}`);
  } catch (e) {
    console.warn(`[funnier-party] relay unavailable: ${e instanceof Error ? e.message : String(e)}`);
  }
}
