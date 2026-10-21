/**
 * PlayPage — /play/:episodeId/seat/:n — a phone-friendly poker seat for a human.
 * Take the seat (seat.join), see your hole cards, act when it's your turn
 * (poker.intent → the dealer in /control applies it). Commands only.
 */
import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { EventConsumer } from '@freaktown/stage-runtime';
import type { CardV1 } from '@freaktown/contracts';
import { createTransport, transportMode } from '../live/transport';
import { CardChip } from './SetStagePage';

interface Turn { seat: number; actions: string[]; to_call: number; min?: number; max?: number; pot: number }

export function PlayPage() {
  const { episodeId = 'demo', seat: seatParam = '4' } = useParams<{ episodeId: string; seat: string }>();
  const seat = Number(seatParam);
  const [search] = useSearchParams();
  const mode = transportMode(search);
  const transport = useMemo(() => createTransport(mode), [mode]);
  const [name, setName] = useState(() => localStorage.getItem('ft_player_name') ?? 'Player');
  const [joined, setJoined] = useState(false);
  const [cards, setCards] = useState<CardV1[]>([]);
  const [turn, setTurn] = useState<Turn | null>(null);
  const [board, setBoard] = useState<CardV1[]>([]);
  const [pot, setPot] = useState(0);
  const [stack, setStack] = useState<number | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [raise, setRaise] = useState(0);
  const [result, setResult] = useState<string | null>(null);

  useEffect(() => {
    const consumer = new EventConsumer({ transport });
    const off = consumer.onEvent((e) => {
      const p = e.payload ?? {};
      switch (e.type) {
        case 'poker.hand_start': setCards([]); setBoard([]); setResult(null); setTurn(null); { const me = (p.seats as Array<{ seat: number; stack: number }>).find((s) => s.seat === seat); if (me) setStack(me.stack); } break;
        case 'poker.deal': if (p.seat === seat) setCards(p.cards as CardV1[]); break;
        case 'poker.turn': setTurn(p.seat === seat ? (p as unknown as Turn) : null); setPot(Number(p.pot ?? 0)); if (p.seat === seat) setRaise(Number(p.min ?? 0)); break;
        case 'poker.action': setPot(Number(p.pot ?? 0)); if (p.seat === seat) { setStack(Number(p.stack)); setTurn(null); } setLog((l) => [`seat ${p.seat} ${p.action}${p.amount ? ' ' + p.amount : ''}`, ...l].slice(0, 6)); break;
        case 'poker.board': setBoard(p.cards as CardV1[]); break;
        case 'poker.showdown': {
          setTurn(null);
          const w = p.winners as Array<{ seat: number; amount: number; ranking: string }>;
          setResult(w.some((x) => x.seat === seat) ? `You win ${w.find((x) => x.seat === seat)!.amount}! (${w.find((x) => x.seat === seat)!.ranking})` : `Seat ${w[0]?.seat} wins (${w[0]?.ranking})`);
          break;
        }
        case 'seat.join': if (p.seat === seat) setJoined(true); break;
      }
    });
    void consumer.connect(episodeId, { role: 'audience', sessionId: `play-${seat}-${Date.now()}` });
    return () => { off(); consumer.disconnect(); };
  }, [transport, episodeId, seat]);

  const join = async () => {
    localStorage.setItem('ft_player_name', name);
    await transport.command('seat.join', { seat, name, avatar_url: 'basic', kind: 'human' });
    setJoined(true);
  };
  const act = (action: string, amount?: number) => { void transport.command('poker.intent', { seat, action, amount }); setTurn(null); };
  const can = (a: string) => !!turn?.actions.includes(a);

  return (
    <div style={page} data-testid="play">
      <div style={{ fontSize: 12, letterSpacing: 3, color: '#7dffa0' }}>FREAK TOWN POKER · SEAT {seat}</div>
      {!joined ? (
        <div style={{ marginTop: 16 }}>
          <input value={name} onChange={(e) => setName(e.target.value)} style={inp} data-testid="play-name" />
          <button style={big('#1b8a3a')} onClick={() => void join()} data-testid="play-join">Take seat {seat}</button>
        </div>
      ) : <div style={{ marginTop: 8, fontSize: 18, fontWeight: 700 }} data-testid="play-joined">{name} · stack {stack ?? '—'}</div>}
      <div style={{ display: 'flex', gap: 8, margin: '16px 0' }} data-testid="play-cards">{cards.map((c, i) => <CardChip key={i} c={c} big />)}{!cards.length && <span style={{ opacity: 0.6 }}>waiting for the deal…</span>}</div>
      <div style={{ fontSize: 14 }}>Board: {board.length ? board.map((c, i) => <CardChip key={i} c={c} />) : '—'} · Pot {pot}</div>
      {turn ? (
        <div style={{ marginTop: 16 }} data-testid="play-turn">
          <div style={{ marginBottom: 8, color: '#ffe14d', fontWeight: 700 }}>Your turn{turn.to_call ? ` · ${turn.to_call} to call` : ''}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <button style={big('#7a1f1f')} onClick={() => act('fold')} disabled={!can('fold')} data-testid="act-fold">Fold</button>
            {can('check')
              ? <button style={big('#2d6cdf')} onClick={() => act('check')} data-testid="act-check">Check</button>
              : <button style={big('#2d6cdf')} onClick={() => act('call')} disabled={!can('call')} data-testid="act-call">Call {turn.to_call}</button>}
            {(can('raise') || can('bet')) && (
              <>
                <input type="range" min={turn.min} max={turn.max} step={10} value={raise} onChange={(e) => setRaise(Number(e.target.value))} style={{ gridColumn: '1 / 3' }} />
                <button style={{ ...big('#c78a00'), gridColumn: '1 / 3' }} onClick={() => act(can('raise') ? 'raise' : 'bet', raise)} data-testid="act-raise">{can('raise') ? 'Raise to' : 'Bet'} {raise}</button>
              </>
            )}
          </div>
        </div>
      ) : <div style={{ marginTop: 16, opacity: 0.7 }} data-testid="play-wait">{result ? '' : 'Not your turn'}</div>}
      {result && <div style={{ marginTop: 16, fontSize: 20, fontWeight: 800, color: '#7dffa0' }} data-testid="play-result">{result}</div>}
      <div style={{ marginTop: 16, fontSize: 12, opacity: 0.7 }}>{log.map((l, i) => <div key={i}>{l}</div>)}</div>
    </div>
  );
}

const page: React.CSSProperties = { minHeight: '100dvh', background: '#0b120d', color: '#eee', fontFamily: 'Inter, system-ui, sans-serif', padding: 18, boxSizing: 'border-box', maxWidth: 520, margin: '0 auto' };
const inp: React.CSSProperties = { width: '100%', boxSizing: 'border-box', background: '#000', color: '#fff', border: '1px solid #335', borderRadius: 8, padding: 12, fontSize: 18, marginBottom: 10 };
const big = (bg: string): React.CSSProperties => ({ background: bg, color: '#fff', border: 'none', borderRadius: 10, padding: '16px 10px', fontSize: 18, fontWeight: 800, width: '100%', cursor: 'pointer' });
