/**
 * SketchPage — load a sketch script, compile it (@funnier/sketch) and play it on a SetStage.
 *
 *   /sketch                          control panel: pick a demo or paste a script, compile, play
 *   /sketch/:id?script=<url>         fetch a funnier.sketch/v1 script, compile in-page, play in realtime
 *   /sketch/:id?demo=<id>            one of the bundled demos (public/sketches/<id>.sketch.json)
 *   ?capture=1                       deterministic: nothing moves until window.__sketch.renderAt(ms)
 *   ?quality=low · ?cpuskin=1 · ?panel=0 (hide the control strip)
 *
 * The stage obeys events only (same doctrine as /newsroom): compiled events go
 * through SetEventExecutor in t_ms order, so a captured frame is a pure
 * function of (script, t). The render CLI (packages/sketch/cli/render.mjs)
 * drives window.__sketch.
 */
import React, { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useParams, useSearchParams } from 'react-router-dom';
import { SetEventExecutor, SetStage, type EventConsumer, type SetStageTelemetry } from '@funnier/stage-runtime';
import { paintWallCard } from '@funnier/newsroom';
import { compileSketch, validateSketch, type CompiledSketch, type SketchScriptV1, type SketchTiming } from '@funnier/sketch';
import type { ShowEvent } from '@funnier/contracts';
import { resolveAsset } from '../live/transport';

export const SKETCH_DEMOS = [
  { id: 'wall-of-news', title: 'Wall of News (news studio)' },
  { id: 'the-tell', title: 'The Tell (poker table)' },
];

declare global {
  interface Window {
    __sketch?: {
      load: (x: SketchScriptV1 | { script: SketchScriptV1; timing?: Partial<SketchTiming> }) => Promise<{ duration_ms: number; estimated: boolean; shots: number; warnings: string[]; set: string }>;
      renderAt: (ms: number) => Promise<void>;
      telemetry: () => (SetStageTelemetry & { t_ms: number }) | null;
      timeline: () => CompiledSketch | null;
      errors: string[];
      ready: boolean;
    };
  }
}

const nullConsumer = { onEvent: () => () => {} } as unknown as EventConsumer;

interface View { t: number; speaker: string | null; line: string; lowerThird: { name: string; title?: string } | null; camera: string }

export function SketchPage() {
  const { sketchId = '' } = useParams();
  const [q] = useSearchParams();
  const capture = q.get('capture') === '1';
  const quality = q.get('quality') === 'low' ? 'low' : 'high';
  const cpuSkinning = q.get('cpuskin') === '1';
  const showPanel = !capture && q.get('panel') !== '0';
  const ref = useRef<HTMLDivElement>(null);
  const apiRef = useRef<NonNullable<Window['__sketch']> | null>(null);
  const playRef = useRef<(() => void) | null>(null);
  const [view, setView] = useState<View>({ t: 0, speaker: null, line: '', lowerThird: null, camera: 'wide' });
  const [status, setStatus] = useState<string>('no sketch loaded');
  const [errors, setErrors] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [demo, setDemo] = useState(q.get('demo') ?? sketchId ?? '');

  useEffect(() => {
    if (!ref.current) return;
    const stage = new SetStage({ container: ref.current, quality, cpuSkinning, manual: true, wallPainter: paintWallCard, resolveUrl: resolveAsset });
    const errs: string[] = [];
    const executor = new SetEventExecutor(stage, nullConsumer, { onError: (m) => errs.push(m) });
    let timeline: CompiledSketch | null = null;
    let cursor = 0;
    let lastT = -1;
    let raf: number | null = null;

    const publish = (t: number) => {
      const o = stage.overlay;
      const tel = stage.telemetry();
      flushSync(() => setView({ t, speaker: o.speaker?.name ?? null, line: o.speaker?.text ?? '', lowerThird: o.lowerThird, camera: tel.camera }));
    };
    const renderAt = async (ms: number): Promise<void> => {
      if (!timeline) return;
      if (ms < lastT) cursor = 0;
      const ev = timeline.events;
      while (cursor < ev.length && ev[cursor].t_ms <= ms) {
        const e = ev[cursor++];
        if (e.type === 'dialogue.line' && e.t_ms + Number(e.payload.duration_ms ?? 0) < ms - 200) continue;
        stage.advanceClock(e.t_ms);
        await executor.execute({ seq: cursor, type: e.type, actor: 'sketch', payload: e.payload } as ShowEvent);
      }
      lastT = ms;
      stage.renderAt(ms);
      publish(ms);
    };
    const load: NonNullable<Window['__sketch']>['load'] = async (x) => {
      const script = 'script' in x ? x.script : x;
      const problems = validateSketch(script);
      if (problems.length) { setErrors(problems); throw new Error(problems.join('; ')); }
      timeline = compileSketch(script, { timing: 'script' in x ? x.timing : undefined });
      cursor = 0; lastT = -1;
      await renderAt(0);
      api.ready = true;
      setErrors(timeline.warnings);
      setStatus(`${timeline.title} · ${(timeline.duration_ms / 1000).toFixed(1)}s · ${timeline.shots.length} shots · ${timeline.timing_source}`);
      return { duration_ms: timeline.duration_ms, estimated: timeline.estimated, shots: timeline.shots.length, warnings: timeline.warnings, set: timeline.set };
    };
    const play = () => {
      if (!timeline) return;
      if (raf !== null) cancelAnimationFrame(raf);
      const t0 = performance.now();
      let busy = false;
      const loop = () => {
        if (!busy) { busy = true; void renderAt(performance.now() - t0).finally(() => { busy = false; }); }
        if (timeline && performance.now() - t0 < timeline.duration_ms + 500) raf = requestAnimationFrame(loop);
      };
      raf = requestAnimationFrame(loop);
    };
    playRef.current = play;
    const api: NonNullable<Window['__sketch']> = {
      load, renderAt, errors: errs, ready: false,
      timeline: () => timeline,
      telemetry: () => ({ ...stage.telemetry(), t_ms: lastT }),
    };
    apiRef.current = api;
    window.__sketch = api;

    const src = q.get('script') ?? (q.get('demo') || sketchId ? `${import.meta.env.BASE_URL}sketches/${q.get('demo') ?? sketchId}.sketch.json` : null);
    if (src) {
      fetch(src).then((r) => r.json()).then(async (j) => {
        setText(JSON.stringify(j, null, 1));
        await load(j as SketchScriptV1);
        if (!capture) play();
      }).catch((e) => setStatus(`load failed: ${e instanceof Error ? e.message : String(e)}`));
    }
    return () => {
      if (raf !== null) cancelAnimationFrame(raf);
      stage.dispose();
      if (window.__sketch === api) delete window.__sketch;
    };
  }, [sketchId, quality, cpuSkinning, capture]);

  const loadDemo = async (id: string) => {
    setDemo(id);
    const j = await (await fetch(`${import.meta.env.BASE_URL}sketches/${id}.sketch.json`)).json();
    setText(JSON.stringify(j, null, 1));
    await apiRef.current?.load(j);
  };
  const loadText = async () => {
    try { await apiRef.current?.load(JSON.parse(text)); } catch (e) { setStatus(`script error: ${e instanceof Error ? e.message : String(e)}`); }
  };

  return (
    <div data-testid="sketch-stage" style={{ width: '100vw', height: '100dvh', position: 'relative', overflow: 'hidden', background: '#07060a', fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif" }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} />
      {view.lowerThird && (
        <div data-testid="lower-third" style={{ position: 'absolute', left: '5%', bottom: '12%', color: '#fff', zIndex: 10, maxWidth: '80%' }}>
          <div style={{ background: '#e8112d', padding: '6px 14px', fontWeight: 800, fontSize: 'clamp(14px, 2.2vw, 24px)' }}>{view.lowerThird.name}</div>
          {view.lowerThird.title && <div style={{ background: 'rgba(8,20,48,0.92)', padding: '6px 14px', fontSize: 'clamp(12px, 1.6vw, 18px)' }}>{view.lowerThird.title}</div>}
        </div>
      )}
      {/* captions: who speaks + the line (also the silent-audio fallback in renders) */}
      {view.speaker && q.get('captions') !== '0' && (
        <div data-testid="sketch-caption" style={{ position: 'absolute', left: '50%', bottom: 'max(18px, 3.5vh)', transform: 'translateX(-50%)', zIndex: 11, maxWidth: 'min(92%, 980px)', textAlign: 'center', color: '#fff', textShadow: '0 2px 6px rgba(0,0,0,0.9)', fontSize: 'clamp(13px, 2vw, 24px)', lineHeight: 1.25, background: 'rgba(0,0,0,0.38)', padding: '4px 12px', borderRadius: 4 }}>
          <b style={{ color: '#F5C86B' }}>{view.speaker}:</b> {view.line}
        </div>
      )}
      {showPanel && (
        <div data-testid="sketch-panel" style={{ position: 'absolute', top: 10, left: 10, zIndex: 20, width: 'min(420px, 92vw)', background: 'rgba(10,10,16,0.86)', color: '#eee', fontSize: 12, padding: 10, borderRadius: 6 }}>
          <div style={{ fontWeight: 700, marginBottom: 6 }}>Sketch control</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <select data-testid="sketch-demo" value={demo} onChange={(e) => void loadDemo(e.target.value)}>
              <option value="">— demo —</option>
              {SKETCH_DEMOS.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
            </select>
            <button data-testid="sketch-compile" onClick={() => void loadText()}>Compile</button>
            <button data-testid="sketch-play" onClick={() => playRef.current?.()}>Play</button>
          </div>
          <textarea data-testid="sketch-script" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false} placeholder="paste a funnier.sketch/v1 script" style={{ width: '100%', height: 120, marginTop: 6, fontFamily: 'ui-monospace, monospace', fontSize: 11, background: '#111', color: '#cfe', border: '1px solid #333' }} />
          <div data-testid="sketch-status" style={{ marginTop: 4 }}>{status}</div>
          <div style={{ opacity: 0.7 }}>t {Math.round(view.t)}ms · cam {view.camera}</div>
          {errors.length > 0 && <div data-testid="sketch-warnings" style={{ color: '#ffd28a', maxHeight: 60, overflow: 'auto' }}>{errors.slice(0, 4).map((e) => <div key={e}>{e}</div>)}</div>}
        </div>
      )}
    </div>
  );
}
