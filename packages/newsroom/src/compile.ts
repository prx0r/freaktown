/**
 * compile(rundown, timings) → a stage event timeline.
 *
 * Output events are the existing set contract (set.load, set.theme,
 * set.camera, overlay.headline / lower_third / ticker, dialogue.line,
 * face.expression, audio.sting) stamped with show time t_ms. Feed them to a
 * SetEventExecutor in order (the newsroom page / render CLI do), or map them
 * to ShowEvents with toShowEvents() for a live room.
 */
import type { CastMemberV1, ShowEvent } from '@funnier/contracts';
import { assertRundown, imageAllowed, type RundownV1, type WallPiece } from './schema';
import { getShowStyle, themePayload, type ShowStyle } from './styles';
import { figureTime, layoutProgram, type Program, type TimingsInput } from './timing';
import { directShots, newsStudioCameras, type CueInfo, type Shot } from './director';

export const TIMELINE_SCHEMA = 'funnier.newsroom.timeline/v1' as const;

export interface TimedEvent { t_ms: number; type: string; payload: Record<string, unknown> }

export interface CompiledShow {
  schema: typeof TIMELINE_SCHEMA;
  rundown_id: string;
  title: string;
  style: string;
  set: string;
  duration_ms: number;
  /** True when any line's timing is an estimate (no measured words). */
  estimated: boolean;
  timing_source: Program['timingSource'];
  wpm: number;
  cadence: { lmin_ms: number; lmax_ms: number; move_ms: number };
  events: TimedEvent[];
  shots: Shot[];
  lines: Array<{ id: string; chair: string; seat: string | null; start_ms: number; end_ms: number; estimated: boolean; storyId: string }>;
  stories: Array<{ id: string; start_ms: number; end_ms: number; headline_ms: number | null; headline: string | null }>;
  warnings: string[];
}

export interface CompileOptions {
  /** Override the rundown's show style (object or id). */
  style?: ShowStyle | string;
  /** Camera table (defaults to the news-studio cues for the cast seats). */
  cameras?: CueInfo[];
}

// event order inside one millisecond: scene first, then graphics, then camera, then speech
const ORDER: Record<string, number> = {
  'set.load': 0, 'set.theme': 1, 'set.auto_director': 2, 'audio.sting': 3, 'overlay.ticker': 4,
  'overlay.headline': 5, 'overlay.lower_third': 6, 'set.camera': 7, 'face.expression': 8, 'dialogue.line': 9,
};

export function compile(rundown: RundownV1, timings: TimingsInput = {}, opts: CompileOptions = {}): CompiledShow {
  assertRundown(rundown);
  const base = typeof opts.style === 'object' ? opts.style : getShowStyle(opts.style ?? rundown.show_style);
  const B = rundown.brand?.trim();
  const style: ShowStyle = B ? { ...base, brand: B, wall: { ...base.wall, brandLine: B.toUpperCase() }, overlay: { ...base.overlay, ticker: { ...base.overlay.ticker, label: B.toUpperCase() }, ...(base.overlay.bug ? { bug: B } : {}) } } : base;
  const C = style.cadence;
  const setId = rundown.set ?? style.set;
  const prog = layoutProgram(rundown, style, timings);
  const warnings: string[] = [];
  if (prog.estimated) warnings.push(`timings ESTIMATED at ${C.wpm} wpm for ${prog.lines.filter((l) => l.estimated).length}/${prog.lines.length} lines (no measured words)`);

  const studioReporters = (rundown.cast.reporters ?? []).filter((r) => r.presence === 'studio' && r.seat);
  const cast: CastMemberV1[] = [
    ...rundown.cast.anchors.map((a) => ({ seat: a.seat, character_id: a.character_id ?? `newsroom.${a.chair}`, name: a.name, avatar_url: a.avatar_url ?? 'basic', kind: 'character' as const })),
    ...studioReporters.map((r) => ({ seat: r.seat!, character_id: `newsroom.${r.chair}`, name: r.name, avatar_url: r.avatar_url ?? 'basic', kind: 'character' as const })),
  ];
  const cameras = opts.cameras ?? newsStudioCameras(cast.map((c) => c.seat));
  const dir = directShots(prog, { cadence: C, cameras, seed: rundown.id });
  warnings.push(...dir.warnings);

  const ev: TimedEvent[] = [];
  const at = (t: number, type: string, payload: Record<string, unknown>) => ev.push({ t_ms: Math.max(0, Math.round(t)), type, payload });

  at(0, 'set.load', { setId, title: rundown.title, cast });
  at(0, 'set.theme', themePayload(style) as unknown as Record<string, unknown>);
  at(0, 'set.auto_director', { on: false });

  // wall cards
  const wallPayload = (w: WallPiece, storyLane?: string): Record<string, unknown> => {
    const p: Record<string, unknown> = { text: w.headline, layout: w.layout ?? 'headline' };
    if (w.kicker) p.kicker = w.kicker;
    if (w.body) p.body = w.body;
    if (w.figure) p.figure = w.figure;
    if (w.credit) p.credit = w.credit;
    const lane = w.image_license ?? storyLane;
    if (w.image_url && imageAllowed(lane)) { p.image_url = w.image_url; p.image_license = lane; }
    return p;
  };
  const storyLane = new Map<string, string | undefined>();
  const storyCountry = new Map<string, string | undefined>();
  rundown.segments.forEach((s) => s.stories.forEach((st) => { storyLane.set(st.id, st.source?.license); storyCountry.set(st.id, st.country); }));

  /** The last wall card shown for each story (restored after reporter/numbers cards). */
  const storyCard = new Map<string, Record<string, unknown>>();
  const headlineAt = new Map<string, { t: number; text: string }>();
  for (const g of prog.graphics) {
    const p = g.piece;
    switch (p.type) {
      case 'wall': {
        const payload = wallPayload(p, storyLane.get(g.storyId));
        at(g.t_ms, 'overlay.headline', payload);
        if ((p.layout ?? 'headline') === 'headline') { storyCard.set(g.storyId, payload); if (!headlineAt.has(g.storyId)) headlineAt.set(g.storyId, { t: g.t_ms, text: p.headline }); }
        break;
      }
      case 'ots':
        at(g.t_ms, 'overlay.headline', { text: p.text, kicker: p.kicker, layout: 'headline' });
        break;
      case 'lower_third':
        at(g.t_ms, 'overlay.lower_third', { name: p.name, title: p.title, show: !p.hide });
        break;
      case 'ticker':
        if (style.overlay.ticker.enabled) at(g.t_ms, 'overlay.ticker', { items: p.items });
        break;
    }
  }
  if (!ev.some((e) => e.type === 'overlay.headline' && e.t_ms === 0)) {
    at(0, 'overlay.headline', { text: rundown.title, kicker: style.brand, layout: 'title' });
  }

  for (const j of prog.jingles) at(j.start_ms, 'audio.sting', { kind: j.kind, asset: j.asset, duration_ms: j.end_ms - j.start_ms });

  // reads
  let anchorIntroduced = false;
  prog.lines.forEach((l, i) => {
    const next = prog.lines[i + 1];
    if (l.seat) {
      at(l.start_ms, 'dialogue.line', {
        seat: l.seat, text: l.text, duration_ms: l.end_ms - l.start_ms, line_id: l.id,
        emotion: l.emotion, words: l.relWords, ...(l.subtitle ? { subtitle: l.subtitle } : {}),
      });
      at(l.start_ms, 'face.expression', { seat: l.seat, emotion: l.emotion ?? style.anchorEmotion, intensity: 0.45, duration_ms: l.end_ms - l.start_ms });
      if (l.kind === 'anchor' && !anchorIntroduced) {
        anchorIntroduced = true;
        at(l.start_ms + 1200, 'overlay.lower_third', { name: l.name, title: style.brand, show: true });
        at(Math.min(l.end_ms, l.start_ms + 1200 + Math.max(6000, C.lmin_ms)), 'overlay.lower_third', { name: l.name, show: false });
      }
    } else {
      // remote reporter: the wall carries them (country card) + their lower third
      const country = l.country ?? storyCountry.get(l.storyId) ?? l.locale ?? 'Correspondent';
      at(l.start_ms, 'overlay.headline', { text: country, kicker: 'From', layout: 'country', body: [l.name, l.locale].filter(Boolean).join(' · ') });
      at(l.start_ms, 'overlay.lower_third', { name: l.name, title: [l.locale, l.country].filter(Boolean).join(' · ') || 'Correspondent', show: true });
      at(l.end_ms, 'overlay.lower_third', { name: l.name, show: false });
      const card = storyCard.get(l.storyId);
      if (card && next && next.storyId === l.storyId) at(l.end_ms + 1, 'overlay.headline', card);
      // the anchor listens (soft nod)
      const anchorSeat = rundown.cast.anchors[0].seat;
      at(l.start_ms + Math.min(2500, (l.end_ms - l.start_ms) / 3), 'face.expression', { seat: anchorSeat, action: 'gesture.nod', intensity: 0.35, duration_ms: 1400 });
    }
    if (l.numbers) {
      // anchor: the card goes up with the line; remote reporter: their country card first, the figure when it is spoken
      const tFig = l.seat ? l.start_ms : Math.max(l.start_ms + Math.min(4000, (l.end_ms - l.start_ms) / 3), figureTime(l) - 300);
      at(tFig, 'overlay.headline', { text: l.numbers.label ?? storyCard.get(l.storyId)?.text ?? 'The numbers', kicker: 'The numbers', layout: 'numbers', figure: l.numbers.figure });
      const card = storyCard.get(l.storyId);
      if (card && next && next.storyId === l.storyId) at(l.end_ms + 1, 'overlay.headline', card);
    }
  });

  // shots
  for (const s of dir.shots) {
    const payload: Record<string, unknown> = { cue: s.cue, source: 'auto_director' };
    if (s.move_ms) { payload.move_ms = s.move_ms; payload.ease = 'smooth'; }
    if (s.creep) { payload.creep = s.creep; payload.creep_ms = s.creep_ms; }
    at(s.start_ms, 'set.camera', payload);
  }

  ev.sort((a, b) => a.t_ms - b.t_ms || (ORDER[a.type] ?? 5) - (ORDER[b.type] ?? 5));

  // On one-shots the wall sits big and cropped behind the anchor: show its ambient
  // state (paper + sunrise, no text) there, and bring the card back on the next wider shot.
  const heads = ev.filter((e) => e.type === 'overlay.headline');
  const logicalAt = (t: number) => { let last: TimedEvent | undefined; for (const h of heads) { if (h.t_ms <= t) last = h; else break; } return last; };
  const extra: TimedEvent[] = [];
  dir.shots.forEach((sh, i) => {
    if (sh.cls !== 'one' && sh.cls !== 'reaction') return;
    const swap = sh.start_ms + Math.round((sh.move_ms ?? 0) * 0.6);
    const card = logicalAt(swap);
    if (card) extra.push({ t_ms: swap, type: 'overlay.headline', payload: { ...card.payload, layout: 'ambient', card_layout: card.payload.layout } });
    for (const h of heads) if (h.t_ms > swap && h.t_ms < sh.end_ms) { h.payload = { ...h.payload, layout: 'ambient', card_layout: h.payload.layout }; }
    const next = dir.shots[i + 1];
    if (next && next.cls !== 'one' && next.cls !== 'reaction') {
      const back = [...heads].reverse().find((h) => h.t_ms <= next.start_ms);
      const fresh = heads.find((h) => h.t_ms > next.start_ms && h.t_ms - next.start_ms <= 1500 && h.payload.layout !== 'ambient');
      if (back && !fresh) extra.push({ t_ms: next.start_ms, type: 'overlay.headline', payload: { ...back.payload, layout: (back.payload.card_layout as string) ?? back.payload.layout, card_layout: undefined } });
    }
  });
  for (const e of extra) { if (e.payload.card_layout === undefined) delete e.payload.card_layout; ev.push(e); }
  // a fresh card arriving just after a cut back to the wall goes up with the cut (no flash of the old card)
  dir.shots.forEach((sh, i) => {
    const prev = dir.shots[i - 1];
    if (!prev || (prev.cls !== 'one' && prev.cls !== 'reaction') || sh.cls === 'one' || sh.cls === 'reaction') return;
    const fresh = heads.find((h) => h.t_ms > sh.start_ms && h.t_ms - sh.start_ms <= 1500 && h.payload.layout !== 'ambient');
    if (fresh) ev.push({ t_ms: sh.start_ms, type: 'overlay.headline', payload: { ...fresh.payload } });
  });
  ev.sort((a, b) => a.t_ms - b.t_ms || (ORDER[a.type] ?? 5) - (ORDER[b.type] ?? 5));
  return {
    schema: TIMELINE_SCHEMA,
    rundown_id: rundown.id,
    title: rundown.title,
    style: style.id,
    set: setId,
    duration_ms: prog.duration_ms,
    estimated: prog.estimated,
    timing_source: prog.timingSource,
    wpm: C.wpm,
    cadence: { lmin_ms: C.lmin_ms, lmax_ms: C.lmax_ms, move_ms: C.move_ms },
    events: ev,
    shots: dir.shots,
    lines: prog.lines.map((l) => ({ id: l.id, chair: l.chair, seat: l.seat, start_ms: l.start_ms, end_ms: l.end_ms, estimated: l.estimated, storyId: l.storyId })),
    stories: prog.stories.map((s) => ({ id: s.id, start_ms: s.start_ms, end_ms: s.end_ms, headline_ms: headlineAt.get(s.id)?.t ?? null, headline: headlineAt.get(s.id)?.text ?? null })),
    warnings,
  };
}

/** Map a compiled timeline to ShowEvents for a live room (created_at = start + t_ms). */
export function toShowEvents(c: CompiledShow, startIso: string, actor = 'newsroom'): ShowEvent[] {
  const t0 = Date.parse(startIso);
  return c.events.map((e, i) => ({ seq: i + 1, type: e.type, actor, payload: e.payload, created_at: new Date(t0 + e.t_ms).toISOString() }));
}

/** Events due in (from, to] — for players that step a clock. */
export function eventsBetween(c: CompiledShow, fromMs: number, toMs: number): TimedEvent[] {
  return c.events.filter((e) => e.t_ms > fromMs && e.t_ms <= toMs);
}
