/**
 * /characters3 — the character studio, read side: browse the characters made
 * through the CHARACTERS MCP server, read their theory, see their sets (lines,
 * roles, delivery cues, revisions) and preview any set on the comedy-club stage
 * (the /sketch player). Data: packages/characters/library/index.json, which the
 * MCP server regenerates on every write. Writing happens through the MCP tools
 * (docs/CHARACTERS-MCP.md); this page never edits.
 *
 *   /characters3                       roster
 *   /characters3/:slug                 one character (theory tab)
 *   /characters3/:slug?tab=sets&set=<id>   a set, with Preview
 */
import React, { useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import catalogJson from '@funnier/characters/catalog';
import { setToSketch, type CharacterSet, type CharacterTheory } from '@funnier/characters';

interface Entry { id: string; name: string; logline: string; origin: string; avatar_url: string; theory: CharacterTheory; theory_md: string; sets: CharacterSet[]; performances: string[] }
const catalog = catalogJson as unknown as { characters: Entry[] };
const slugOf = (id: string) => id.replace(/^[a-z]+\./, '');

const C = { bg: '#07060a', panel: '#14131c', line: '#2a2836', text: '#f3f1ec', dim: '#9a98a8', pink: '#ff2fa8', cyan: '#7BDFF2', gold: '#F5C86B' };
const box = { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, padding: 14 } as const;

/** Tiny markdown → React for the generated THEORY.md (headings, bullets, bold, code, quotes). */
function Md({ src }: { src: string }) {
  const inline = (s: string, k: string) => s.split(/(\*\*[^*]+\*\*|`[^`]+`|_[^_]+_)/g).map((p, i) =>
    p.startsWith('**') ? <b key={`${k}${i}`}>{p.slice(2, -2)}</b> : p.startsWith('`') ? <code key={`${k}${i}`} style={{ color: C.cyan }}>{p.slice(1, -1)}</code> : p.startsWith('_') && p.endsWith('_') && p.length > 2 ? <i key={`${k}${i}`}>{p.slice(1, -1)}</i> : p);
  return (
    <div style={{ fontSize: 14, lineHeight: 1.55 }}>
      {src.split('\n').map((l, i) => {
        const k = String(i);
        if (l.startsWith('# ')) return <h2 key={k} style={{ margin: '4px 0 8px', color: C.gold }}>{l.slice(2)}</h2>;
        if (l.startsWith('## ')) return <h3 key={k} style={{ margin: '18px 0 6px', color: C.pink, fontSize: 13, letterSpacing: 1.5, textTransform: 'uppercase' }}>{l.slice(3)}</h3>;
        if (l.startsWith('> ')) return <div key={k} style={{ color: C.dim, fontSize: 12 }}>{inline(l.slice(2), k)}</div>;
        const m = l.match(/^(\s*)(- |\d+\. )(.*)$/);
        if (m) return <div key={k} style={{ paddingLeft: 12 + m[1].length * 8, textIndent: -10 }}>{m[2].startsWith('-') ? '· ' : m[2]}{inline(m[3], k)}</div>;
        if (!l.trim()) return <div key={k} style={{ height: 6 }} />;
        return <div key={k}>{inline(l, k)}</div>;
      })}
    </div>
  );
}

function Roster() {
  return (
    <div data-testid="characters-roster" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12, marginTop: 12 }}>
      {catalog.characters.map((c) => (
        <Link key={c.id} to={`/characters3/${slugOf(c.id)}`} data-testid={`character-card-${slugOf(c.id)}`} style={{ ...box, color: C.text, textDecoration: 'none', display: 'block' }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <div style={{ width: 38, height: 38, borderRadius: 19, background: `linear-gradient(135deg, ${(c.theory.props.length ? C.gold : C.cyan)}, ${C.pink})` }} />
            <div>
              <div style={{ fontWeight: 700 }}>{c.name}</div>
              <div style={{ fontSize: 11.5, color: C.dim }}>{c.id} · {c.origin} · {c.theory.physicality.delivery_default}</div>
            </div>
          </div>
          <p style={{ fontSize: 13, color: '#d8d6e0', margin: '10px 0 6px' }}>{c.logline}</p>
          <div style={{ fontSize: 12, color: C.cyan }}>{c.sets.length} set{c.sets.length === 1 ? '' : 's'} · {c.performances.length} performance{c.performances.length === 1 ? '' : 's'} · {c.theory.arc.appearances.length} appearances</div>
        </Link>
      ))}
      {!catalog.characters.length && <p style={{ color: C.dim }}>No characters yet. Create one with the MCP tool <code>character_create</code>.</p>}
    </div>
  );
}

function SetView({ entry, set }: { entry: Entry; set: CharacterSet }) {
  const [preview, setPreview] = useState<string | null>(null);
  const play = () => {
    const sk = setToSketch(set, { look: { avatar_url: entry.avatar_url, palette: [] } });
    const url = URL.createObjectURL(new Blob([JSON.stringify(sk)], { type: 'application/json' }));
    setPreview(`${import.meta.env.BASE_URL}sketch/${sk.id}?panel=0&script=${encodeURIComponent(url)}`);
  };
  let beat = -1;
  return (
    <div style={{ display: 'grid', gridTemplateColumns: preview ? 'minmax(0,1fr) minmax(0,1fr)' : '1fr', gap: 12 }}>
      <div style={box} data-testid="set-view">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
          <b>{set.title}</b>
          <span style={{ fontSize: 12, color: C.dim }}>{set.length_min} min · ~{set.seconds}s · {set.status} · {set.revisions.length} revision(s)</span>
        </div>
        <div style={{ display: 'flex', gap: 8, margin: '10px 0' }}>
          <button data-testid="set-preview" onClick={play} style={btn}>Preview on stage</button>
          {set.performance && <Link to={`/sketch/${set.performance}`} style={{ ...btnGhost, textDecoration: 'none' }}>Play submitted performance</Link>}
        </div>
        {set.lines.map((l) => {
          const b = set.beats.find((x) => x.n === l.beat);
          const head = l.beat !== beat ? <div style={{ fontSize: 11, color: C.gold, margin: '12px 0 2px', textTransform: 'uppercase', letterSpacing: 1 }}>Beat {l.beat} · {b?.kind}{b?.kind === 'bit' ? ` · ${b.topic} · ${b.move}` : ''}</div> : null;
          beat = l.beat;
          return (
            <React.Fragment key={l.id}>
              {head}
              <div data-testid={`set-line-${l.id}`} style={{ display: 'grid', gridTemplateColumns: '70px 1fr', gap: 6, padding: '4px 0', borderTop: `1px solid #1d1c26` }}>
                <span style={{ fontSize: 10.5, color: l.role === 'punch' || l.role === 'callback' ? C.pink : C.dim, textTransform: 'uppercase', paddingTop: 2 }}>{l.role}</span>
                <div>
                  <div style={{ fontSize: 14 }}>{l.text}</div>
                  <div style={{ fontSize: 11, color: C.dim }}>{l.delivery}{l.pause_ms ? ` · pause ${l.pause_ms}` : ''}{l.hold_ms ? ` · hold ${l.hold_ms}` : ''}{l.emphasis.length ? ` · hit "${l.emphasis.join(' ')}"` : ''} · {l.id}</div>
                </div>
              </div>
            </React.Fragment>
          );
        })}
        {set.revisions.length > 0 && (
          <div style={{ marginTop: 14, fontSize: 12.5 }}>
            <div style={{ color: C.gold, marginBottom: 4 }}>REVISIONS</div>
            {set.revisions.map((r, i) => <div key={i} style={{ marginBottom: 6 }}><b>{i + 1}.</b> “{r.notes}”<div style={{ color: C.dim }}>{r.changes.join(' · ')}</div></div>)}
          </div>
        )}
      </div>
      {preview && <iframe data-testid="set-stage" title="preview" src={preview} style={{ width: '100%', aspectRatio: '16/9', border: 0, borderRadius: 10, background: '#000', position: 'sticky', top: 12 }} />}
    </div>
  );
}

function CharacterView({ entry }: { entry: Entry }) {
  const [q, setQ] = useSearchParams();
  const tab = q.get('tab') ?? 'theory';
  const setId = q.get('set') ?? entry.sets[entry.sets.length - 1]?.id;
  const set = entry.sets.find((s) => s.id === setId);
  const t = entry.theory;
  const tabBtn = (id: string, label: string) => <button data-testid={`tab-${id}`} onClick={() => setQ({ tab: id, ...(id === 'sets' && setId ? { set: setId } : {}) })} style={id === tab ? btn : btnGhost}>{label}</button>;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ ...box, display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: '1 1 320px' }}>
          <div style={{ fontSize: 22, fontWeight: 800 }}>{entry.name}</div>
          <div style={{ color: '#d8d6e0', fontSize: 14 }}>{entry.logline}</div>
          <div style={{ fontSize: 12, color: C.dim, marginTop: 4 }}>wants <b style={{ color: C.text }}>{t.comic_want}</b> · flaw <b style={{ color: C.text }}>{t.flaw.flaw.split(':')[0]}</b> · status plays {t.status.plays} · {t.physicality.delivery_default}</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>{tabBtn('theory', 'Theory')}{tabBtn('sets', `Sets (${entry.sets.length})`)}</div>
      </div>
      {tab === 'theory' && <div style={{ ...box, marginTop: 12 }} data-testid="theory-view"><Md src={entry.theory_md} /></div>}
      {tab === 'sets' && (
        <div style={{ marginTop: 12 }}>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
            {entry.sets.map((s) => <button key={s.id} data-testid={`set-tab-${s.id}`} onClick={() => setQ({ tab: 'sets', set: s.id })} style={s.id === setId ? btn : btnGhost}>{s.title.slice(0, 40)} ({s.length_min}m)</button>)}
          </div>
          {set ? <SetView key={set.id} entry={entry} set={set} /> : <p style={{ color: C.dim }}>No sets yet. Write one with <code>set_write</code>.</p>}
        </div>
      )}
    </div>
  );
}

export function CharactersPage() {
  const { slug } = useParams();
  const nav = useNavigate();
  const entry = useMemo(() => catalog.characters.find((c) => slugOf(c.id) === slug), [slug]);
  return (
    <div data-testid="characters-page" style={{ minHeight: '100dvh', background: C.bg, color: C.text, fontFamily: "Inter, 'Helvetica Neue', Arial, sans-serif", padding: '20px clamp(12px,3vw,40px)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 13, letterSpacing: 2, color: C.pink, cursor: 'pointer' }} onClick={() => nav('/characters3')}>FUNNIER · /CHARACTERS3 STUDIO</div>
        <div style={{ fontSize: 12, color: C.dim }}>{catalog.characters.length} characters · written via the CHARACTERS MCP server</div>
      </div>
      {slug && !entry && <p style={{ color: C.dim }}>No character “{slug}”. <Link to="/characters3" style={{ color: C.cyan }}>Back to the roster</Link>.</p>}
      {entry ? <CharacterView entry={entry} /> : !slug && <Roster />}
    </div>
  );
}

const btn = { background: C.pink, color: '#fff', border: 0, borderRadius: 8, padding: '7px 12px', fontWeight: 700, cursor: 'pointer', fontSize: 13 } as const;
const btnGhost = { background: 'transparent', color: '#fff', border: '1px solid #555', borderRadius: 8, padding: '7px 12px', cursor: 'pointer', fontSize: 13 } as const;
