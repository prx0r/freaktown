/**
 * WatchPage — one URL to watch a set. /watch/:setId (default buddha).
 *
 * The stage and the control panel are the same-origin iframes, so the
 * local BroadcastChannel link works between them inside ONE tab — this
 * page just opens both and lets the control's ?auto= start the show.
 * Stage gets the click-to-unlock gesture pass-through (autoplay policy).
 */
import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

const SETS = ['buddha-ultimate-deadpan', 'captain-ata-ashcroft', 'the-algorithm'];

export function WatchPage() {
  const { setId = 'buddha-ultimate-deadpan' } = useParams<{ setId: string }>();
  const [search] = useSearchParams();
  const nav = useNavigate();
  const ep = 'watch';
  const stageSrc = `/stage/${ep}?transport=local&quality=low`;
  const ctrlSrc = `/control/${ep}?transport=local&auto=${encodeURIComponent(setId)}`;
  const note = useRef<HTMLDivElement>(null);

  // Click anywhere = unlock audio in the stage iframe (both frames get the
  // gesture because they share this origin/user activation).
  useEffect(() => {
    const unlock = () => {
      for (const f of document.querySelectorAll('iframe')) {
        try { (f.contentWindow as Window & { __audioUnlock?: () => void })?.__audioUnlock?.(); } catch { /* cross-frame best effort */ }
      }
      if (note.current) note.current.style.display = 'none';
    };
    window.addEventListener('pointerdown', unlock, { once: true });
    return () => window.removeEventListener('pointerdown', unlock);
  }, []);

  return (
    <div style={{ position: 'fixed', inset: 0, background: '#05030a' }}>
      <iframe title="stage" src={stageSrc} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }} />
      <iframe title="control" src={ctrlSrc} style={{ position: 'absolute', width: 1, height: 1, opacity: 0, border: 0, left: -9999 }} />
      <div ref={note} style={{ position: 'absolute', left: '50%', bottom: 18, transform: 'translateX(-50%)', color: '#cfc7e0', background: 'rgba(10,8,16,.82)', border: '1px solid #2a2438', borderRadius: 999, padding: '8px 18px', fontSize: 14, pointerEvents: 'none', zIndex: 5 }}>
        click anywhere for sound · {setId}
      </div>
      <div style={{ position: 'absolute', right: 14, top: 12, zIndex: 5, display: 'flex', gap: 8 }}>
        <select
          value={setId}
          onChange={(e) => nav(`/watch/${e.target.value}`)}
          style={{ background: '#16131f', color: '#eee', border: '1px solid #3a3350', borderRadius: 6, padding: '6px 10px', fontSize: 13 }}
        >
          {SETS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>
    </div>
  );
}
