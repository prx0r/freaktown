/**
 * NewsroomPage — program feed for a compiled newsroom show (@funnier/newsroom).
 *
 *   /newsroom/:showId?rundown=<url>      fetch a rundown.json, compile in-page, play in realtime
 *   /newsroom/:showId?timeline=<url>     fetch an already-compiled timeline
 *   ?capture=1                           deterministic: nothing moves until window.__newsroom.renderAt(ms)
 *   ?t=<ms>                              (capture) render this instant on load (screenshots)
 *   ?quality=low · ?cpuskin=1 · ?debug=1
 *
 * The stage obeys events only: compiled events go through SetEventExecutor
 * in t_ms order; the themed overlays (lower third, ticker, bug) are drawn
 * here from the stage's overlay state + the show clock, so a captured frame
 * is a pure function of (timeline, t).
 */
import React, { useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { useParams, useSearchParams } from 'react-router-dom';
import { SetEventExecutor, SetStage, type EventConsumer, type SetStageTelemetry } from '@funnier/stage-runtime';
import { compile, paintWallCard, preloadWallImages, type CompiledShow, type RundownV1, type TimingsInput } from '@funnier/newsroom';
import type { SetThemePayloadV1, ShowEvent } from '@funnier/contracts';
import { resolveAsset } from '../live/transport';

type LoadInput = CompiledShow | { rundown: RundownV1; timings?: TimingsInput };

declare global {
  interface Window {
    __newsroom?: {
      load: (x: LoadInput) => Promise<{ duration_ms: number; estimated: boolean; shots: number; warnings: string[]; timing_source: string }>;
      renderAt: (ms: number) => Promise<void>;
      telemetry: () => (SetStageTelemetry & { t_ms: number; wall: { text: string; layout: string } | null }) | null;
      timeline: () => CompiledShow | null;
      errors: string[];
      ready: boolean;
    };
  }
}

interface View {
  t: number;
  theme: SetThemePayloadV1 | null;
  lowerThird: { name: string; title?: string; at: number } | null;
  ticker: string[];
  headline: { text: string; layout: string; kicker?: string } | null;
  /** Subtitle of the line being spoken (when the rundown gives one). */
  subtitle: { text: string; who: string } | null;
}

const nullConsumer = { onEvent: () => () => {} } as unknown as EventConsumer;

export function NewsroomPage() {
  const { showId = 'show' } = useParams();
  const [q] = useSearchParams();
  const capture = q.get('capture') === '1';
  const quality = q.get('quality') === 'low' ? 'low' : 'high';
  const cpuSkinning = q.get('cpuskin') === '1';
  const debug = q.get('debug') === '1';
  const ref = useRef<HTMLDivElement>(null);
  const tickerRef = useRef<HTMLDivElement>(null);
  const [view, setView] = useState<View>({ t: 0, theme: null, lowerThird: null, ticker: [], headline: null, subtitle: null });
  const subs = q.get('subs') !== '0';
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const stage = new SetStage({ container: ref.current, quality, cpuSkinning, manual: true, wallPainter: paintWallCard, resolveUrl: resolveAsset });
    const executor = new SetEventExecutor(stage, nullConsumer, { onError: (m) => errors.push(m) });
    const errors: string[] = [];
    let timeline: CompiledShow | null = null;
    let cursor = 0;
    let lastT = -1;
    let ltAt = 0;
    let ltKey = '';
    let raf: number | null = null;

    const publish = (t: number) => {
      const o = stage.overlay;
      const key = o.lowerThird ? `${o.lowerThird.name}|${o.lowerThird.title ?? ''}` : '';
      if (key !== ltKey) { ltKey = key; ltAt = t; }
      const v: View = {
        t,
        theme: o.theme ?? null,
        lowerThird: o.lowerThird ? { ...o.lowerThird, at: ltAt } : null,
        ticker: o.ticker,
        headline: o.headline ? { text: o.headline.text, layout: String(o.headline.layout ?? 'headline'), kicker: o.headline.kicker } : null,
        subtitle: subtitleAt(t),
      };
      flushSync(() => setView(v));
    };

    const seatName = new Map<string, string>();
    const subtitleAt = (t: number): View['subtitle'] => {
      if (!timeline) return null;
      for (let i = timeline.events.length - 1; i >= 0; i--) {
        const e = timeline.events[i];
        if (e.type !== 'dialogue.line' || e.t_ms > t) continue;
        if (t > e.t_ms + Number(e.payload.duration_ms ?? 0) + 250) return null;
        return e.payload.subtitle ? { text: String(e.payload.subtitle), who: seatName.get(String(e.payload.seat)) ?? '' } : null;
      }
      return null;
    };

    const renderAt = async (ms: number): Promise<void> => {
      if (!timeline) return;
      if (ms < lastT) { cursor = 0; } // seek back: replay from the top
      const ev = timeline.events;
      while (cursor < ev.length && ev[cursor].t_ms <= ms) {
        const e = ev[cursor++];
        // seeking: skip dialogue lines that are already over
        if (e.type === 'dialogue.line' && e.t_ms + Number(e.payload.duration_ms ?? 0) < ms - 200) continue;
        stage.advanceClock(e.t_ms);
        await executor.execute({ seq: cursor, type: e.type, actor: 'newsroom', payload: e.payload } as ShowEvent);
      }
      lastT = ms;
      stage.renderAt(ms);
      publish(ms);
    };

    const load = async (x: LoadInput) => {
      timeline = 'events' in x ? x : compile(x.rundown, x.timings ?? {});
      cursor = 0; lastT = -1;
      seatName.clear();
      for (const e of timeline.events) if (e.type === 'set.load' || e.type === 'set.cast') for (const c of (e.payload.cast as Array<{ seat: string; name?: string }> | undefined) ?? []) if (c.name) seatName.set(c.seat, c.name);
      await preloadWallImages(timeline.events.filter((e) => e.type === 'overlay.headline' && e.payload.image_url).map((e) => String(e.payload.image_url)));
      await renderAt(0);
      api.ready = true;
      return { duration_ms: timeline.duration_ms, estimated: timeline.estimated, shots: timeline.shots.length, warnings: timeline.warnings, timing_source: timeline.timing_source };
    };

    const api: NonNullable<Window['__newsroom']> = {
      load, renderAt, errors, ready: false,
      timeline: () => timeline,
      telemetry: () => {
        const tel = stage.telemetry();
        const h = stage.overlay.headline;
        return { ...tel, t_ms: lastT, wall: h ? { text: h.text, layout: String(h.layout ?? 'headline') } : null };
      },
    };
    window.__newsroom = api;

    const src = q.get('rundown') ?? q.get('timeline');
    if (src) {
      fetch(src).then((r) => r.json()).then(async (j) => {
        await load(q.get('timeline') ? (j as CompiledShow) : { rundown: j as RundownV1 });
        const t = Number(q.get('t') ?? NaN);
        if (capture) { if (Number.isFinite(t)) await renderAt(t); return; }
        const t0 = performance.now();
        let busy = false;
        const loop = () => {
          if (!busy) { busy = true; void renderAt(performance.now() - t0).finally(() => { busy = false; }); }
          if (timeline && performance.now() - t0 < timeline.duration_ms) raf = requestAnimationFrame(loop);
        };
        raf = requestAnimationFrame(loop);
      }).catch((e) => setErr(`load failed: ${e instanceof Error ? e.message : String(e)}`));
    }
    return () => {
      if (raf !== null) cancelAnimationFrame(raf);
      stage.dispose();
      if (window.__newsroom === api) delete window.__newsroom;
    };
  }, [showId, quality, cpuSkinning, capture]);

  const th = view.theme;
  const P = { paper: '#f6efe2', ink: '#2a2420', accent: '#F5C86B', bg: '#07060a', ...(th?.palette ?? {}) };
  const serif = th?.fonts?.display ?? "Georgia, 'C059', 'DejaVu Serif', serif";
  const paper = th?.overlay?.lowerThird === 'paper';
  const tick = th?.overlay?.ticker;
  const ltAge = view.lowerThird ? view.t - view.lowerThird.at : 0;
  const ltOpacity = Math.max(0, Math.min(1, ltAge / (paper ? 900 : 250)));
  const tickerW = tickerRef.current?.scrollWidth ?? 2000;
  const tickerX = -(((view.t / 1000) * (tick?.speed_px_s ?? 40)) % Math.max(1, tickerW / 2));

  return (
    <div data-testid="newsroom-stage" data-style={th?.style ?? ''} style={{ width: '100vw', height: '100dvh', position: 'relative', overflow: 'hidden', background: P.bg, fontFamily: serif }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} />

      {/* screen-reader / test mirror of the wall card (the wall itself is a 3D canvas texture) */}
      <div data-testid="wall-headline" data-layout={view.headline?.layout ?? ''} style={srOnly}>{view.headline?.text ?? ''}</div>

      {th?.overlay?.bug && (
        <div data-testid="bug" style={{ position: 'absolute', top: 'max(14px, 2.2vh)', left: 'max(14px, 2.2vw)', color: P.paper, background: 'rgba(7,6,10,0.62)', padding: '4px 10px', borderRadius: 2, fontSize: 'clamp(11px, 1.4vw, 17px)', letterSpacing: '0.12em', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: 8, zIndex: 10 }}>
          <span style={{ width: '0.6em', height: '0.6em', borderRadius: '50%', background: P.accent, display: 'inline-block' }} />{th.overlay.bug}
        </div>
      )}

      {view.lowerThird && (
        paper ? (
          <div data-testid="lower-third" style={{ position: 'absolute', left: '5%', bottom: tick?.enabled && view.ticker.length ? 'calc(clamp(26px, 4.2vh, 38px) + 4%)' : '7%', zIndex: 10, maxWidth: 'min(80%, 640px)', opacity: ltOpacity, transform: `translateY(${(1 - ltOpacity) * 8}px)`, background: P.paper, color: P.ink, borderLeft: `6px solid ${P.accent}`, padding: 'clamp(6px, 1.2vh, 12px) clamp(12px, 1.8vw, 22px)', boxShadow: '0 6px 24px rgba(0,0,0,0.35)' }}>
            <div style={{ fontWeight: 600, fontSize: 'clamp(15px, 2.1vw, 26px)', lineHeight: 1.15 }}>{view.lowerThird.name}</div>
            {view.lowerThird.title && <div style={{ fontStyle: 'italic', fontSize: 'clamp(12px, 1.5vw, 18px)', opacity: 0.8, marginTop: 2 }}>{view.lowerThird.title}</div>}
          </div>
        ) : (
          <div data-testid="lower-third" style={{ position: 'absolute', left: '5%', bottom: '15%', color: '#fff', zIndex: 10, maxWidth: '80%', opacity: ltOpacity, fontFamily: serif }}>
            <div style={{ background: P.accent2 ?? '#e8112d', padding: '6px 14px', fontWeight: 800, fontSize: 'clamp(14px, 2.2vw, 24px)' }}>{view.lowerThird.name}</div>
            {view.lowerThird.title && <div style={{ background: 'rgba(8,20,48,0.92)', padding: '6px 14px', fontSize: 'clamp(12px, 1.6vw, 18px)' }}>{view.lowerThird.title}</div>}
          </div>
        )
      )}

      {subs && view.subtitle && (
        <div data-testid="subtitle" style={{ position: 'absolute', left: '50%', bottom: tick?.enabled && view.ticker.length ? 'calc(clamp(26px, 4.2vh, 38px) + 3.5%)' : '5%', transform: 'translateX(-50%)', zIndex: 11, maxWidth: 'min(88%, 980px)', textAlign: 'center', background: 'rgba(0,0,0,0.72)', color: '#fff7c2', padding: '6px 14px', borderRadius: 4, fontFamily: "Inter, Arial, 'DejaVu Sans', sans-serif", fontSize: 'clamp(14px, 2.1vw, 26px)', lineHeight: 1.3, textShadow: '0 2px 4px #000' }}>
          {view.subtitle.text}
        </div>
      )}

      {tick?.enabled && view.ticker.length > 0 && (
        <div data-testid="ticker" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 'clamp(26px, 4.2vh, 38px)', display: 'flex', zIndex: 10, background: paper ? 'rgba(7,6,10,0.82)' : 'rgba(5,12,30,0.95)', color: paper ? P.paper : '#fff', borderTop: `1px solid ${P.accent}`, fontSize: 'clamp(11px, 1.4vw, 16px)' }}>
          <div style={{ background: P.accent, color: paper ? P.ink : '#111', fontWeight: 700, padding: '0 12px', display: 'flex', alignItems: 'center', letterSpacing: '0.08em', whiteSpace: 'nowrap', zIndex: 2 }}>{tick.label ?? ''}</div>
          <div style={{ overflow: 'hidden', flex: 1, position: 'relative' }}>
            <div ref={tickerRef} style={{ position: 'absolute', whiteSpace: 'nowrap', top: '50%', transform: `translate(${tickerX}px, -50%)`, paddingLeft: 24 }}>
              {[...view.ticker, ...view.ticker].join('     ·     ')}
            </div>
          </div>
        </div>
      )}

      {debug && (
        <div style={{ position: 'absolute', top: 12, right: 12, zIndex: 20, color: '#9fffb0', fontSize: 11, fontFamily: 'ui-monospace, monospace', background: 'rgba(0,0,0,0.7)', padding: '6px 8px' }} data-testid="newsroom-debug">
          t {Math.round(view.t)}ms · wall [{view.headline?.layout}] {view.headline?.text}
        </div>
      )}
      {err && <div style={{ position: 'absolute', bottom: 48, right: 12, color: '#ffb3b3', zIndex: 20 }}>{err}</div>}
    </div>
  );
}

const srOnly: React.CSSProperties = { position: 'absolute', width: 1, height: 1, overflow: 'hidden', clip: 'rect(0 0 0 0)', whiteSpace: 'nowrap' };
