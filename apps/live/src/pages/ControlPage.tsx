/**
 * ControlPage — operator console.
 *
 * INVARIANT: control never mutates stage state directly. Every button is a
 * canonical command through ONE LiveTransport (ControlClient):
 *   local mode → LocalRoom (BroadcastChannel) · room mode → EpisodeRoom DO.
 * The log/phase panels are a READ view of the same room.
 *
 * URL: /control/:episodeId?transport=local|room
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { EventConsumer, LocalTransport } from '@funnier/stage-runtime';
import type { ShowEvent } from '@funnier/contracts';
import { ControlClient } from '../control/controlClient';
import { SetsPanel } from '../control/SetsPanel';
import { adminKey, createTransport, loadSetCatalog, setAdminKey, transportMode, type SetEntry } from '../live/transport';

const CAMERAS: Array<{ id: string; label: string; key: string }> = [
  { id: 'WIDE_STAGE', label: 'Wide', key: '1' },
  { id: 'COMIC_MEDIUM', label: 'Mid', key: '2' },
  { id: 'COMIC_CLOSE', label: 'Close-up', key: '3' },
  { id: 'SIDE_STAGE', label: 'Side', key: '4' },
];
const REACTIONS = ['laugh', 'clap', 'groan', 'boo', 'crickets'] as const;
const AVATARS: Array<{ id: string; label: string }> = [
  { id: '', label: 'Set default' },
  { id: 'avatars/default-v1.vrm', label: 'VRM · default-v1' },
  { id: 'basic', label: 'BASIC · human' },
  { id: 'basic:robot', label: 'BASIC · robot' },
];

type ShowState = 'idle' | 'loading' | 'waiting_stage' | 'live' | 'paused' | 'ended';

export function ControlPage() {
  const { episodeId = 'demo' } = useParams<{ episodeId: string }>();
  const [search] = useSearchParams();
  const mode = transportMode(search);

  const [key, setKey] = useState(adminKey);
  const [sets, setSets] = useState<SetEntry[]>([]);
  const [setId, setSetId] = useState<string>('');
  const [avatarOverride, setAvatarOverride] = useState('');
  const [events, setEvents] = useState<ShowEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [show, setShow] = useState<ShowState>('idle');
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [stageLink, setStageLink] = useState<string | null>(null);
  const [perfId, setPerfId] = useState<string | null>(null);
  const [camera, setCamera] = useState('WIDE_STAGE');
  const [stageAvatar, setStageAvatar] = useState<string | null>(null);

  const transport = useMemo(() => createTransport(mode, { authKey: key }), [mode, key]);
  const client = useMemo(() => new ControlClient(transport), [transport]);
  const readyWaiters = useRef(new Map<string, () => void>());
  const startedRef = useRef<string | null>(null);
  const perfIdRef = useRef<string | null>(null);

  useEffect(() => { void loadSetCatalog().then((s) => { setSets(s); setSetId((cur) => cur || s[0]?.id || ''); }).catch((e) => setNotice(String(e))); }, []);

  // ?auto=<setId> — one-click watch links (see /watch/:setId): once the
  // sets are loaded AND the room link is up, start that show without a click.
  const autoSet = search.get('auto');
  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoSet || autoRan.current || !connected || !sets.length) return;
    if (show !== 'idle') return;
    if (!sets.some((s) => s.id === autoSet)) { setNotice(`unknown set: ${autoSet}`); return; }
    autoRan.current = true;
    setSetId(autoSet);
    const timer = window.setTimeout(() => { void startShow(autoSet); }, 400);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSet, connected, sets, show]);

  // READ view of the room (same transport the commands go through).
  useEffect(() => {
    const consumer = new EventConsumer({ transport });
    setEvents([]);
    const off = consumer.onEvent((e) => {
      setEvents((prev) => [...prev.slice(-199), e]);
      if (e.type === 'camera.cut' && typeof e.payload?.camera === 'string') setCamera(e.payload.camera);
      if (e.type === 'performance.ready') {
        const pid = e.payload?.performance_id as string | undefined;
        const av = e.payload?.avatar as { kind?: string; name?: string; mouthMode?: string } | undefined;
        if (av) setStageAvatar(`${av.kind}:${av.name} · mouth ${av.mouthMode}`);
        if (pid) { readyWaiters.current.get(pid)?.(); readyWaiters.current.delete(pid); }
      }
    });
    const offSnap = consumer.onSnapshot((s) => { if (s.seq === 0) setEvents([]); });
    consumer.connect(episodeId, { role: 'audience', sessionId: `control-${Date.now()}` })
      .then(() => setConnected(true))
      .catch(() => { setConnected(false); setNotice(mode === 'room' ? 'EpisodeRoom unreachable (wrangler dev on :8787?)' : 'local link failed'); });
    const timer = window.setInterval(() => setConnected(consumer.connected), 1500);
    return () => { window.clearInterval(timer); off(); offSnap(); consumer.disconnect(); };
  }, [transport, episodeId, mode]);

  const run = useCallback(async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label); setNotice(null);
    try { await fn(); } catch (e) { setNotice(`${label}: ${e instanceof Error ? e.message : String(e)}`); }
    finally { setBusy(null); }
  }, []);

  const current = sets.find((s) => s.id === setId);

  const waitReady = (pid: string, ms: number) => new Promise<boolean>((resolve) => {
    const t = window.setTimeout(() => { readyWaiters.current.delete(pid); resolve(false); }, ms);
    readyWaiters.current.set(pid, () => { window.clearTimeout(t); resolve(true); });
  });

  const startShow = (setIdArg?: string) => run('start', async () => {
    const entry = (setIdArg ? sets.find((s) => s.id === setIdArg) : undefined) ?? current;
    if (!entry) throw new Error('pick a set');
    const pid = `${entry.id}-${Date.now().toString(36)}`;
    setPerfId(pid);
    perfIdRef.current = pid;
    setShow('loading');
    await client.startShow(entry.title);
    const ready = waitReady(pid, 45000);
    await client.preloadPerformance({
      performance_id: pid,
      set_url: entry.set_url,
      audio_url: entry.audio_url,
      avatar_url: avatarOverride || entry.avatar_url,
      character_name: entry.character_name,
      title: entry.premise,
      episode_id: episodeId,
    });
    setShow('waiting_stage');
    if (!(await ready)) {
      if (startedRef.current !== pid) setNotice('No stage acknowledged the preload — open the stage link, then press Go.');
      return;
    }
    await go(pid);
  });

  const go = async (pid = perfIdRef.current) => {
    if (!pid || startedRef.current === pid) return; // never start a performance twice
    startedRef.current = pid;
    await client.enterCharacter(pid);
    await client.startPerformance(pid);
    setShow('live');
  };

  const pause = () => run('pause', async () => { await client.pauseShow(); setShow('paused'); });
  const resume = () => run('resume', async () => { await client.resumeShow(); setShow('live'); });
  const end = () => run('end', async () => {
    if (perfId) { await client.endPerformance(perfId); await client.exitCharacter(perfId); }
    await client.endShow();
    setShow('ended');
  });
  const cut = (cam: string) => run(`cut ${cam}`, () => client.cutCamera(cam));
  const react = (r: string) => run(`react ${r}`, () => client.triggerReaction(r));
  const rimshot = () => run('rimshot', () => client.playSfx('rimshot'));
  const reset = () => {
    if (transport instanceof LocalTransport) { transport.reset(); setEvents([]); setShow('idle'); setPerfId(null); }
  };
  const mintStage = () => run('mint', async () => {
    const tok = await client.mintStageToken('stage');
    const base = `${window.location.origin}${import.meta.env.BASE_URL}stage/${episodeId}?transport=${mode}`;
    setStageLink(tok ? `${base}&token=${encodeURIComponent(tok)}` : base);
  });

  // Hotkeys: 1-4 camera, space pause/resume, L laugh — all as commands.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return;
      const c = CAMERAS.find((x) => x.key === e.key);
      if (c) { void cut(c.id); return; }
      if (e.key === 'l') void react('laugh');
      if (e.key === ' ') { e.preventDefault(); if (show === 'live') void pause(); else if (show === 'paused') void resume(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  const stageHref = `${import.meta.env.BASE_URL}stage/${episodeId}?transport=${mode}`;

  return (
    <div style={page} data-testid="control">
      <header style={header}>
        <div>
          <div style={{ fontSize: 12, letterSpacing: 3, color: '#ff7ac8' }}>FUNNIER · CONTROL</div>
          <h1 style={{ margin: '2px 0 0', fontSize: 22 }}>Episode <code>{episodeId}</code></h1>
        </div>
        <div style={{ textAlign: 'right', fontSize: 13 }}>
          <span style={pill(connected ? '#1f7a3a' : '#7a1f1f')} data-testid="link-status">
            {mode === 'local' ? 'LOCAL LINK' : 'EPISODE ROOM'} · {connected ? 'connected' : 'offline'}
          </span>
          <div style={{ marginTop: 6 }}>
            <Link to={stageHref} target="_blank" style={{ color: '#9fd8ff' }}>open stage ↗</Link>
          </div>
        </div>
      </header>

      <SetsPanel episodeId={episodeId} mode={mode} authKey={key} />

      <section style={card}>
        <h2 style={h2}>Act / set <span style={{ fontSize: 12, opacity: 0.6 }}>(comedy club)</span></h2>
        <div style={row}>
          <select value={setId} onChange={(e) => setSetId(e.target.value)} style={input} data-testid="set-select">
            {sets.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}
          </select>
          <select value={avatarOverride} onChange={(e) => setAvatarOverride(e.target.value)} style={input} data-testid="avatar-select">
            {AVATARS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
          </select>
        </div>
        {current && (
          <div style={{ fontSize: 13, opacity: 0.8, marginTop: 8 }}>
            {current.beats} beats · {(current.duration_ms / 1000).toFixed(1)}s · body: {avatarOverride || current.avatar_note}
          </div>
        )}
      </section>

      <section style={card}>
        <h2 style={h2}>Show <span style={pill('#333')} data-testid="show-state">{show}</span></h2>
        <div style={row}>
          <button style={btn('#ff2fa0')} onClick={() => void startShow()} disabled={!!busy || show === 'loading' || show === 'waiting_stage'} data-testid="start">▶ Start show</button>
          {show === 'waiting_stage' && <button style={btn('#c78a00')} onClick={() => run('go', () => go())}>Go anyway</button>}
          <button style={btn('#444')} onClick={pause} disabled={show !== 'live'} data-testid="pause">❚❚ Pause</button>
          <button style={btn('#444')} onClick={resume} disabled={show !== 'paused'} data-testid="resume">▶ Resume</button>
          <button style={btn('#7a1f1f')} onClick={end} disabled={show === 'idle' || show === 'ended'} data-testid="end">■ End</button>
          {mode === 'local' && <button style={btn('#222')} onClick={reset} data-testid="reset">New show (clear log)</button>}
        </div>
        {stageAvatar && <div style={{ fontSize: 12, opacity: 0.75, marginTop: 8 }} data-testid="stage-avatar">stage ready · {stageAvatar}</div>}
      </section>

      <section style={card}>
        <h2 style={h2}>Camera <span style={{ fontSize: 12, opacity: 0.6 }}>(keys 1–4 · plan auto-cuts run on the stage)</span></h2>
        <div style={row}>
          {CAMERAS.map((c) => (
            <button key={c.id} style={btn(camera === c.id ? '#2d6cdf' : '#333')} onClick={() => cut(c.id)} data-testid={`cam-${c.id}`}>
              {c.key} · {c.label}
            </button>
          ))}
        </div>
      </section>

      <section style={card}>
        <h2 style={h2}>Crowd</h2>
        <div style={row}>
          {REACTIONS.map((r) => (
            <button key={r} style={btn('#3a2a55')} onClick={() => react(r)} data-testid={`react-${r}`}>{r}</button>
          ))}
          <button style={btn('#3a2a55')} onClick={rimshot}>ba-dum-tss</button>
        </div>
      </section>

      {mode === 'room' && (
        <section style={card}>
          <h2 style={h2}>EpisodeRoom auth</h2>
          <div style={row}>
            <input style={{ ...input, flex: 2 }} type="password" placeholder="admin key (ft_…) or Privy JWT" value={key}
              onChange={(e) => { setKey(e.target.value); setAdminKey(e.target.value); }} />
            <button style={btn('#2d6cdf')} onClick={mintStage}>Mint stage link</button>
          </div>
          {stageLink && <div style={{ fontSize: 12, wordBreak: 'break-all', marginTop: 8 }}><a href={stageLink} target="_blank" rel="noreferrer" style={{ color: '#9fd8ff' }}>{stageLink}</a></div>}
        </section>
      )}

      {notice && <div style={noticeBox} data-testid="notice">{notice}</div>}

      <section style={card}>
        <h2 style={h2}>Event log <span style={{ fontSize: 12, opacity: 0.6 }}>(persisted, replayable)</span></h2>
        <div style={logBox} data-testid="event-log">
          {[...events].reverse().slice(0, 40).map((e) => (
            <div key={e.seq} style={{ display: 'flex', gap: 10 }}>
              <span style={{ opacity: 0.5, width: 34, textAlign: 'right' }}>{e.seq}</span>
              <span style={{ color: '#ffd27a', minWidth: 150 }}>{e.type}</span>
              <span style={{ opacity: 0.7, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {summary(e)}
              </span>
            </div>
          ))}
          {!events.length && <div style={{ opacity: 0.5 }}>no events yet</div>}
        </div>
      </section>
    </div>
  );
}

function summary(e: ShowEvent): string {
  const p = e.payload ?? {};
  if (e.type === 'camera.cut') return String(p.camera);
  if (e.type === 'crowd.reaction') return String(p.reaction);
  if (e.type === 'performance.preload') return `${p.set_url} · ${p.avatar_url}`;
  if (e.type === 'performance.ready') return `${p.performance_id} (${e.actor})`;
  if (e.type === 'show.start') return String(p.title ?? '');
  return Object.keys(p).length ? JSON.stringify(p).slice(0, 80) : '';
}

const page: React.CSSProperties = {
  minHeight: '100vh', background: '#0c0a12', color: '#eee', fontFamily: 'Inter, system-ui, sans-serif',
  padding: '18px clamp(12px, 3vw, 32px)', boxSizing: 'border-box', maxWidth: 980, margin: '0 auto',
};
const header: React.CSSProperties = { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 14, gap: 12 };
const card: React.CSSProperties = { background: '#16131f', border: '1px solid #2a2438', borderRadius: 10, padding: '12px 14px', marginBottom: 12 };
const h2: React.CSSProperties = { margin: '0 0 10px', fontSize: 15, fontWeight: 700, display: 'flex', gap: 10, alignItems: 'center' };
const row: React.CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 8 };
const input: React.CSSProperties = { flex: 1, minWidth: 200, background: '#0c0a12', color: '#eee', border: '1px solid #3a3350', borderRadius: 6, padding: '8px 10px', fontSize: 14 };
const btn = (bg: string): React.CSSProperties => ({ background: bg, color: '#fff', border: 'none', borderRadius: 6, padding: '9px 14px', fontSize: 14, fontWeight: 600, cursor: 'pointer' });
const pill = (bg: string): React.CSSProperties => ({ background: bg, color: '#fff', borderRadius: 999, padding: '3px 10px', fontSize: 12, fontWeight: 600 });
const noticeBox: React.CSSProperties = { background: '#3a2a10', border: '1px solid #7a5a20', color: '#ffd9a0', borderRadius: 8, padding: '8px 12px', marginBottom: 12, fontSize: 13 };
const logBox: React.CSSProperties = { fontFamily: 'ui-monospace, monospace', fontSize: 12, maxHeight: 260, overflowY: 'auto', lineHeight: 1.6 };
