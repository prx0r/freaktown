/**
 * /minute — write-a-minute: premise → the agent drafts a ~60 s bit in its voice →
 * you tweak text + delivery per line (or ask the agent to suggest) → preview on the
 * comedy-club stage (the /sketch player) → submit as a performance (funnier.sketch/v1).
 * Submissions are saved in this browser (localStorage) and downloadable as JSON.
 */
import React, { useMemo, useState } from 'react';
import { draftMinute, listPartyIdentities, minuteSeconds, submitMinute, suggestDelivery, type LineDelivery, type MinuteDraft, type MinuteLine } from '@funnier/party';

const DELIVERIES: LineDelivery[] = ['deadpan', 'deliberate', 'manic', 'warm', 'conspiratorial', 'pause'];
const DEMO = 'users have infinite demands and no manners';

export function MinutePage() {
  const ids = useMemo(() => listPartyIdentities(), []);
  const [performer, setPerformer] = useState(ids.find((i) => i.id === 'agent.hark-lantern')?.id ?? ids[0]?.id ?? '');
  const [premise, setPremise] = useState(DEMO);
  const [m, setM] = useState<MinuteDraft | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [status, setStatus] = useState('');
  const idn = ids.find((i) => i.id === performer)!;

  const draft = () => { setM(draftMinute(premise, idn)); setPreview(null); setStatus('Drafted by the agent. Edit anything.'); };
  const edit = (id: string, patch: Partial<MinuteLine>) => setM((x) => (x ? { ...x, lines: x.lines.map((l) => (l.id === id ? { ...l, ...patch } : l)) } : x));
  const suggest = () => { setM((x) => (x ? { ...x, lines: suggestDelivery(x.lines, idn) } : x)); setStatus('Delivery re-suggested by the agent (your emphasis kept).'); };
  const sub = () => (m ? submitMinute(m, idn.look.avatar_url) : null);
  const doPreview = () => {
    const s = sub();
    if (!s) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(s.performance)], { type: 'application/json' }));
    setPreview(`${import.meta.env.BASE_URL}sketch/${s.performance.id}?panel=0&script=${encodeURIComponent(url)}`);
  };
  const submit = () => {
    const s = sub();
    if (!s) return;
    const all = JSON.parse(localStorage.getItem('funnier.minutes') ?? '[]');
    all.push(s);
    localStorage.setItem('funnier.minutes', JSON.stringify(all));
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(s, null, 1)], { type: 'application/json' }));
    a.download = `${s.performance.id}.performance.json`;
    a.click();
    setStatus(`Submitted "${s.performance.title}" (${s.seconds}s) as a performance: saved in this browser + downloaded.`);
  };

  const box = { background: '#14131c', border: '1px solid #2a2836', borderRadius: 10, padding: 12 } as const;
  const inp = { background: '#0d0c12', color: '#f3f1ec', border: '1px solid #333', borderRadius: 6, padding: '6px 8px', fontSize: 13 } as const;
  return (
    <div data-testid="minute-page" style={{ minHeight: '100dvh', background: '#07060a', color: '#f3f1ec', fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif", padding: '20px clamp(12px,3vw,40px)' }}>
      <div style={{ fontSize: 13, letterSpacing: 2, color: '#ff2fa8' }}>FUNNIER · WRITE A MINUTE</div>
      <div style={{ ...box, marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <input data-testid="minute-premise" value={premise} onChange={(e) => setPremise(e.target.value)} style={{ ...inp, flex: '1 1 320px' }} />
        <select data-testid="minute-performer" value={performer} onChange={(e) => setPerformer(e.target.value)} style={inp}>
          {ids.map((i) => <option key={i.id} value={i.id}>{i.name}{i.origin === 'agent-made' ? ' (agent-made)' : ''}</option>)}
        </select>
        <button data-testid="minute-draft" onClick={draft} style={btn}>Draft</button>
        {m && <><button data-testid="minute-suggest" onClick={suggest} style={btnGhost}>Suggest delivery</button><button data-testid="minute-preview" onClick={doPreview} style={btnGhost}>Preview on stage</button><button data-testid="minute-submit" onClick={submit} style={btn}>Submit</button></>}
      </div>
      {status && <div data-testid="minute-status" style={{ fontSize: 12.5, color: '#7BDFF2', margin: '8px 2px' }}>{status}</div>}
      <div style={{ display: 'grid', gridTemplateColumns: preview ? 'minmax(0,1fr) minmax(0,1fr)' : '1fr', gap: 12, marginTop: 8 }}>
        {m && (
          <div style={box} data-testid="minute-lines">
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}><b>{m.title}</b><span style={{ color: '#9a98a8', fontSize: 12 }}>{idn.name} · ~{minuteSeconds(m.lines)}s</span></div>
            {m.lines.map((l) => (
              <div key={l.id} data-testid={`minute-line-${l.id}`} style={{ display: 'grid', gridTemplateColumns: '64px 1fr', gap: 6, padding: '6px 0', borderTop: '1px solid #222' }}>
                <span style={{ fontSize: 10.5, color: l.role === 'punch' || l.role === 'callback' ? '#ff2fa8' : '#9a98a8', textTransform: 'uppercase', paddingTop: 6 }}>{l.role}</span>
                <div>
                  <textarea value={l.text} onChange={(e) => edit(l.id, { text: e.target.value })} rows={1} style={{ ...inp, width: '100%', resize: 'vertical', fontFamily: 'inherit' }} />
                  <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap', fontSize: 11.5, color: '#9a98a8', alignItems: 'center' }}>
                    <select value={l.delivery} onChange={(e) => edit(l.id, { delivery: e.target.value as LineDelivery })} style={{ ...inp, padding: '2px 4px', fontSize: 11.5 }}>{DELIVERIES.map((d) => <option key={d}>{d}</option>)}</select>
                    pause <input type="number" step={100} value={l.pause_ms} onChange={(e) => edit(l.id, { pause_ms: Number(e.target.value) })} style={{ ...inp, width: 64, padding: '2px 4px' }} />
                    hold <input type="number" step={100} value={l.hold_ms} onChange={(e) => edit(l.id, { hold_ms: Number(e.target.value) })} style={{ ...inp, width: 64, padding: '2px 4px' }} />
                    emphasis <input value={l.emphasis.join(' ')} onChange={(e) => edit(l.id, { emphasis: e.target.value.split(/\s+/).filter(Boolean), emphasis_user: true })} style={{ ...inp, width: 110, padding: '2px 4px' }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {preview && <iframe data-testid="minute-stage" title="preview" src={preview} style={{ width: '100%', aspectRatio: '16/9', border: 0, borderRadius: 10, background: '#000' }} />}
      </div>
      {!m && <p style={{ color: '#9a98a8' }}>Pick a performer, write a premise, and let the agent draft a minute. Everything it writes is original; you edit the rest.</p>}
    </div>
  );
}

const btn = { background: '#ff2fa8', color: '#fff', border: 0, borderRadius: 8, padding: '8px 14px', fontWeight: 700, cursor: 'pointer' } as const;
const btnGhost = { background: 'transparent', color: '#fff', border: '1px solid #555', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' } as const;
