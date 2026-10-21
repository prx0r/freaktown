/**
 * SetStagePage — program feed for multi-seat sets (news studio, podcast,
 * poker table). Mounted by StagePage when the room's latest `set.load`
 * names a set other than the comedy club. Obeys events only (SetEventExecutor).
 *   ?debug=1  telemetry · ?quality=low · ?cpuskin=1 · ?setglb=1 (load unverified CC0 GLB decor)
 */
import React, { useEffect, useRef, useState } from 'react';
import { EventConsumer, SetEventExecutor, SetStage, type SetStageTelemetry } from '@funnier/stage-runtime';
import type { CardV1 } from '@funnier/contracts';
import { createTransport, resolveAsset, type TransportMode } from '../live/transport';

declare global {
  interface Window {
    __setStage?: { stage: SetStage; executor: SetEventExecutor; telemetry: () => SetStageTelemetry; errors: string[]; consumer?: EventConsumer };
  }
}

export function SetStagePage(props: { episodeId: string; mode: TransportMode; token?: string; debug: boolean; quality: 'high' | 'low'; cpuSkinning: boolean; glb: boolean }) {
  const { episodeId, mode, token, debug, quality, cpuSkinning, glb } = props;
  const ref = useRef<HTMLDivElement>(null);
  const [tele, setTele] = useState<SetStageTelemetry | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const transport = createTransport(mode);
    const consumer = new EventConsumer({ transport });
    const stage = new SetStage({ container: ref.current, quality, cpuSkinning, glb, resolveUrl: resolveAsset });
    const errors: string[] = [];
    const executor = new SetEventExecutor(stage, consumer, { onError: (m) => { errors.push(m); console.warn('[set executor]', m); } });
    executor.attach();
    window.__setStage = { stage, executor, telemetry: () => stage.telemetry(), errors, consumer } as typeof window.__setStage;
    consumer.connect(episodeId, { role: 'stage', token }).catch(() => setErr('link failed'));
    const timer = window.setInterval(() => setTele(stage.telemetry()), 200);
    return () => {
      window.clearInterval(timer);
      executor.detach();
      consumer.disconnect();
      stage.dispose();
      if (window.__setStage?.stage === stage) delete window.__setStage;
    };
  }, [episodeId, mode, token, quality, cpuSkinning, glb]);

  const o = tele?.overlay;
  const poker = tele?.poker;
  return (
    <div data-testid="set-stage" data-set={tele?.setId ?? ''} style={{ width: '100vw', height: '100dvh', position: 'relative', overflow: 'hidden', background: '#000', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <div ref={ref} style={{ position: 'absolute', inset: 0 }} />

      {tele?.setId === 'news-studio' && o?.lowerThird && (
        <div style={lowerThird} data-testid="lower-third">
          <div style={{ background: '#e8112d', padding: '6px 14px', fontWeight: 800, fontSize: 'clamp(14px, 2.2vw, 24px)' }}>{o.lowerThird.name}</div>
          {o.lowerThird.title && <div style={{ background: 'rgba(8,20,48,0.92)', padding: '6px 14px', fontSize: 'clamp(12px, 1.6vw, 18px)' }}>{o.lowerThird.title}</div>}
        </div>
      )}
      {tele?.setId === 'news-studio' && !!o?.ticker.length && (
        <div style={tickerBar} data-testid="ticker">
          <div style={{ background: '#ffcc33', color: '#111', fontWeight: 800, padding: '0 12px', display: 'flex', alignItems: 'center', zIndex: 2 }}>FREAK NEWS</div>
          <div style={{ overflow: 'hidden', flex: 1, position: 'relative' }}>
            <div style={tickerText}>{[...o.ticker, ...o.ticker].join('   •   ')}</div>
          </div>
        </div>
      )}

      {tele?.setId === 'podcast' && (
        <>
          <div style={onAir} data-testid="on-air">● ON AIR · FREAK TALK</div>
          {o?.speaker && tele.activeSpeaker && (
            <div style={strap} data-testid="speaker-strap">
              <div style={{ fontWeight: 800 }}>{o.speaker.name}</div>
              <div style={{ fontSize: '0.8em', opacity: 0.9 }}>{o.speaker.text}</div>
            </div>
          )}
        </>
      )}

      {poker && (
        <div style={hud} data-testid="poker-hud">
          <div style={{ fontWeight: 800, letterSpacing: 1 }}>POT {poker.pot} · {poker.street.toUpperCase()}</div>
          <div style={{ display: 'flex', gap: 4, margin: '4px 0' }}>{poker.board.map((c, i) => <CardChip key={i} c={c} />)}</div>
          {Object.entries(poker.names).map(([seat, name]) => (
            <div key={seat} style={{ opacity: poker.folded.includes(Number(seat)) ? 0.45 : 1, color: poker.toAct === Number(seat) ? '#ffe14d' : '#fff' }}>
              {poker.toAct === Number(seat) ? '▶ ' : ''}{name} · {poker.stacks[Number(seat)] ?? '—'}{poker.button === Number(seat) ? ' (D)' : ''}
            </div>
          ))}
          {poker.lastAction && <div style={{ marginTop: 4, color: '#9fd8ff' }} data-testid="poker-last">{poker.names[poker.lastAction.seat] ?? `seat ${poker.lastAction.seat}`} {poker.lastAction.action}{poker.lastAction.amount ? ` ${poker.lastAction.amount}` : ''}</div>}
          {!!poker.winners.length && <div style={{ marginTop: 4, color: '#7dffa0', fontWeight: 800 }} data-testid="poker-winner">🏆 {poker.winners.map((w) => `${poker.names[w.seat] ?? w.seat} +${w.amount} (${w.ranking})`).join(', ')}</div>}
        </div>
      )}

      {debug && tele && (
        <div style={debugBox} data-testid="set-debug">
          <div>{tele.setId} · cam {tele.camera} · cuts {tele.cuts.length} · auto {String(tele.autoDirector)}</div>
          <div>{tele.environment}{tele.envError ? ` (${tele.envError})` : ''} · {tele.fps} fps</div>
          {tele.seats.map((s) => <div key={s.seat}>{s.seat}: {s.name} [{s.avatar}/{s.mouthMode}] {s.speaking ? `talking ${s.mouth.toFixed(2)}` : ''}</div>)}
        </div>
      )}
      {err && <div style={{ position: 'absolute', bottom: 12, right: 12, color: '#ffb3b3' }}>{err}</div>}
    </div>
  );
}

const SUIT: Record<string, string> = { spades: '♠', clubs: '♣', hearts: '♥', diamonds: '♦' };
export function CardChip({ c, big }: { c: CardV1; big?: boolean }) {
  const red = c.suit === 'hearts' || c.suit === 'diamonds';
  return <span style={{ background: '#fff', color: red ? '#d01020' : '#111', borderRadius: 4, padding: big ? '10px 12px' : '1px 5px', fontWeight: 800, fontSize: big ? 28 : 14, minWidth: big ? 44 : 0, textAlign: 'center', display: 'inline-block' }}>{c.rank === 'T' ? '10' : c.rank}{SUIT[c.suit]}</span>;
}

const lowerThird: React.CSSProperties = { position: 'absolute', left: '5%', bottom: '15%', color: '#fff', zIndex: 10, maxWidth: '80%' };
const tickerBar: React.CSSProperties = { position: 'absolute', left: 0, right: 0, bottom: 0, height: 'clamp(28px, 4.5vh, 40px)', display: 'flex', background: 'rgba(5,12,30,0.95)', color: '#fff', zIndex: 10, fontSize: 'clamp(12px, 1.6vw, 18px)', borderTop: '2px solid #ffcc33' };
const tickerText: React.CSSProperties = { position: 'absolute', whiteSpace: 'nowrap', top: '50%', transform: 'translateY(-50%)', animation: 'ftTicker 28s linear infinite', paddingLeft: '100%' };
const onAir: React.CSSProperties = { position: 'absolute', top: 14, right: 14, background: '#d01020', color: '#fff', fontWeight: 800, padding: '4px 10px', borderRadius: 4, fontSize: 13, zIndex: 10 };
const strap: React.CSSProperties = { position: 'absolute', left: '4%', bottom: '6%', color: '#fff', zIndex: 10, maxWidth: '80%', background: 'linear-gradient(90deg, rgba(255,90,138,0.9), rgba(40,20,30,0.75))', borderLeft: '4px solid #ffd9a8', padding: '8px 14px', fontSize: 'clamp(13px, 2vw, 20px)' };
const hud: React.CSSProperties = { position: 'absolute', top: 12, left: 12, zIndex: 10, color: '#fff', background: 'rgba(0,0,0,0.6)', padding: '8px 12px', borderRadius: 8, fontSize: 'clamp(11px, 1.4vw, 14px)', lineHeight: 1.5, maxWidth: '46%' };
const debugBox: React.CSSProperties = { position: 'absolute', top: 12, right: 12, zIndex: 20, color: '#9fffb0', fontSize: 11, fontFamily: 'ui-monospace, monospace', background: 'rgba(0,0,0,0.7)', padding: '6px 8px', borderRadius: 4 };
