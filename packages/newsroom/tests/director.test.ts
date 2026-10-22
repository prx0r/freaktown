import { describe, expect, it } from 'vitest';
import { compile, getShowStyle, isLegalCut, layoutProgram, estimateWords, newsStudioCameras, type CompiledShow, type RundownV1, type Shot } from '../src';
import goodnight from './fixtures/rundown.goodnight.json';
import brisk from './fixtures/rundown.default-news.json';

const fixtures: Array<[string, RundownV1]> = [['goodnight', goodnight as RundownV1], ['default-news', brisk as RundownV1]];

function shotAt(shots: Shot[], t: number): Shot {
  const s = shots.find((x) => t >= x.start_ms && t < x.end_ms);
  if (!s) throw new Error(`no shot at ${t}`);
  return s;
}

describe.each(fixtures)('director invariants (%s)', (styleId, rd) => {
  const style = getShowStyle(styleId);
  const C = style.cadence;
  const out: CompiledShow = compile(rd);
  const prog = layoutProgram(rd, style);
  const cams = newsStudioCameras(['anchor1']);
  const camOf = (cue: string) => cams.find((c) => c.cue === cue)!;

  it('covers the whole show contiguously from 0', () => {
    expect(out.shots[0].start_ms).toBe(0);
    for (let i = 1; i < out.shots.length; i++) expect(out.shots[i].start_ms).toBe(out.shots[i - 1].end_ms);
    expect(out.shots[out.shots.length - 1].end_ms).toBe(out.duration_ms);
  });

  it('keeps shot lengths inside [lmin, lmax] (open/close holds + silence exempt, forced shots reported)', () => {
    const bad = out.shots.filter((s) => {
      const d = s.end_ms - s.start_ms;
      const speech = prog.lines.some((l) => l.start_ms < s.end_ms && l.end_ms > s.start_ms);
      return speech && s.reason !== 'open' && s.reason !== 'close' && (d < C.lmin_ms || d > C.lmax_ms);
    });
    expect(bad.every((s) => s.forced)).toBe(true);
    expect(bad.length).toBeLessThanOrEqual(1);
    expect(out.warnings.filter((w) => w.startsWith('shot ')).length).toBe(bad.length);
  });

  it('never cuts mid-word or inside the last 0.5s of a line', () => {
    for (const s of out.shots) {
      expect(isLegalCut(s.start_ms, prog.lines, C.tail_hold_ms), `cut ${s.cue} @${s.start_ms}`).toBe(true);
      for (const l of prog.lines) if (s.start_ms > l.start_ms && s.start_ms < l.end_ms) expect(s.start_ms).toBeLessThanOrEqual(l.end_ms - 500);
    }
  });

  it('keeps the speaker in shot (remote reporter = the wall, or a reaction cut-away)', () => {
    for (const l of prog.lines) for (const w of l.words) {
      const s = shotAt(out.shots, w.start_ms);
      const c = camOf(s.cue);
      if (l.seat) expect(c.seats, `${l.id} word "${w.word}" @${w.start_ms} in ${s.cue}`).toContain(l.seat);
      else expect(c.wall || c.cls === 'reaction', `${l.id} remote @${w.start_ms} in ${s.cue}`).toBe(true);
    }
  });

  it('shows the wall headline before each story cuts to the single', () => {
    const sections = out.stories.filter((s) => ['s1', 's2', 's3'].includes(s.id));
    expect(sections).toHaveLength(3);
    for (const st of sections) {
      expect(st.headline_ms).not.toBeNull();
      const inStory = out.shots.filter((s) => s.end_ms > st.start_ms && s.start_ms < st.end_ms);
      const firstRead = out.lines.find((l) => l.storyId === st.id)!.start_ms;
      const opening = shotAt(out.shots, firstRead);
      expect(['wide', 'ots']).toContain(opening.cls);
      const firstSingle = inStory.find((s) => s.cls === 'one' && s.start_ms >= st.start_ms);
      if (firstSingle) expect(st.headline_ms!).toBeLessThanOrEqual(firstSingle.start_ms);
      const headlineEv = out.events.find((e) => e.type === 'overlay.headline' && e.t_ms === st.headline_ms);
      expect(headlineEv).toBeTruthy();
      expect(headlineEv!.t_ms).toBeLessThanOrEqual(firstRead);
    }
  });

  it('opens on the wide then pushes in; closes with a slow pull-out to the wide', () => {
    expect(out.shots[0].cue).toBe('wide');
    expect(out.shots[0].reason).toBe('open');
    expect(out.shots[1].reason).toBe('push-in');
    expect(out.shots[1].cls).toBe('one');
    expect(out.shots[1].move_ms).toBeGreaterThan(0);
    const last = out.shots[out.shots.length - 1];
    expect(out.shots[out.shots.length - 2].cls).not.toBe('wide'); // a closer framing first, so the pull-out reads
    expect(out.shots.some((s) => s.cls === 'one' && s.start_ms >= out.lines[out.lines.length - 1].start_ms - 1000)).toBe(true); // settle on the anchor for the close
    expect(last.cue).toBe('wide');
    expect(last.reason).toBe('close');
    expect(last.move_ms).toBe(C.close_pull_ms);
  });

  it('a number line puts the numbers card on the wall in an over-the-shoulder shot', () => {
    const nl = prog.lines.find((l) => l.numbers)!;
    const ev = out.events.find((e) => e.type === 'overlay.headline' && e.payload.layout === 'numbers');
    expect(ev!.t_ms).toBeLessThanOrEqual(nl.start_ms); // with the line, or with the cut back to the wall just before it
    expect(ev!.t_ms).toBeGreaterThanOrEqual(nl.start_ms - 1500);
    expect(ev?.payload.figure).toBe('75–1');
    expect(camOf(shotAt(out.shots, nl.words[0].start_ms).cue).wall).toBe(true);
  });

  it('section change = sting + wide', () => {
    const sting = out.events.find((e) => e.type === 'audio.sting' && e.payload.kind === 'sting')!;
    expect(shotAt(out.shots, sting.t_ms).cue).toBe('wide');
  });

  it('remote reporter: country card on the wall + name/locale lower third', () => {
    const rl = prog.lines.find((l) => l.kind === 'reporter')!;
    const card = out.events.find((e) => e.t_ms === rl.start_ms && e.type === 'overlay.headline');
    expect(card?.payload).toMatchObject({ layout: 'country', text: 'Kenya' });
    const lt = out.events.find((e) => e.t_ms === rl.start_ms && e.type === 'overlay.lower_third');
    expect(lt?.payload).toMatchObject({ name: 'Test Reporter', show: true });
    expect(String(lt?.payload.title)).toContain('EN-KE');
    expect(out.events.some((e) => e.type === 'dialogue.line' && e.payload.text === rl.text)).toBe(false);
  });

  it('licence lanes gate wall images', () => {
    const s1 = out.events.find((e) => e.type === 'overlay.headline' && e.t_ms === out.stories.find((s) => s.id === 's1')!.headline_ms);
    const s2 = out.events.find((e) => e.type === 'overlay.headline' && e.t_ms === out.stories.find((s) => s.id === 's2')!.headline_ms);
    expect(s1?.payload.image_url).toBeUndefined(); // fact-rewrite
    expect(s2?.payload.image_url).toBe('https://example.org/img2.jpg'); // verbatim-ok
  });

  it('mixes one-shots with wider shots and penalises repeats', () => {
    const classes = new Set(out.shots.map((s) => s.cls));
    expect(classes.has('one')).toBe(true);
    expect(classes.has('wide') && classes.has('ots')).toBe(true);
    for (let i = 1; i < out.shots.length; i++) if (!out.shots[i].move_ms) expect(out.shots[i].cue === out.shots[i - 1].cue && out.shots[i].reason === 'ed').toBe(false);
  });

  it('one-shots show the wall ambient (no cropped text); the card returns on the next wider shot', () => {
    for (let i = 0; i < out.shots.length - 1; i++) {
      const sh = out.shots[i];
      if (sh.cls !== 'one') continue;
      const inside = out.events.filter((e) => e.type === 'overlay.headline' && e.t_ms > sh.start_ms + (sh.move_ms ?? 0) && e.t_ms < sh.end_ms);
      expect(inside.every((e) => e.payload.layout === 'ambient')).toBe(true);
      const next = out.shots[i + 1];
      if (next.cls !== 'one' && next.cls !== 'reaction') {
        const back = out.events.filter((e) => e.type === 'overlay.headline' && e.t_ms === next.start_ms);
        expect(back.length === 0 || back.some((e) => e.payload.layout !== 'ambient')).toBe(true);
      }
    }
  });

  it('is deterministic', () => {
    expect(JSON.stringify(compile(rd))).toBe(JSON.stringify(out));
  });
});

describe('cadence profiles', () => {
  it('goodnight holds far longer than default-news, with eased moves', () => {
    const g = compile(goodnight as RundownV1), n = compile(brisk as RundownV1);
    const mean = (c: CompiledShow) => c.shots.reduce((a, s) => a + (s.end_ms - s.start_ms), 0) / c.shots.length;
    expect(mean(g)).toBeGreaterThan(mean(n) * 1.6);
    expect(g.cadence).toEqual({ lmin_ms: 7000, lmax_ms: 16000, move_ms: 2400 });
    expect(n.cadence.lmin_ms).toBe(2500);
    expect(n.cadence.lmax_ms).toBe(6000);
    expect(g.shots.some((s) => s.creep)).toBe(true);
    expect(n.shots.filter((s) => s.reason === 'ed').every((s) => !s.move_ms)).toBe(true);
  });
});

describe('timing', () => {
  it('estimates at the style wpm and flags it', () => {
    const w = estimateWords('one two three four five six seven eight nine ten.', 105);
    expect(w).toHaveLength(10);
    expect(w[9].end_ms).toBeGreaterThan(5000);
    expect(w[9].end_ms).toBeLessThanOrEqual(Math.round((10 * 60000) / 105) + 1);
    const out = compile(goodnight as RundownV1);
    expect(out.estimated).toBe(true);
    expect(out.timing_source).toBe('estimated');
    expect(out.warnings[0]).toMatch(/ESTIMATED at 105 wpm/);
  });
  it('prefers measured words (per piece, per line id, or episode words.json aligned in order)', () => {
    const rd = JSON.parse(JSON.stringify(goodnight)) as RundownV1;
    const read = rd.segments[0].stories[0].pieces[3] as { text: string; id?: string };
    read.id = 'open-line';
    const toks = read.text.split(/\s+/);
    const words = toks.map((word, i) => ({ word, start_ms: i * 300, end_ms: i * 300 + 250 }));
    const out = compile(rd, { lines: { 'open-line': words } });
    const line = out.lines.find((l) => l.id === 'open-line')!;
    expect(line.estimated).toBe(false);
    expect(line.end_ms - line.start_ms).toBe(words[words.length - 1].end_ms);
    expect(out.timing_source).toBe('mixed');

    // episode-wide words.json: every read measured → not estimated
    const p = layoutProgram(rd, getShowStyle('goodnight'));
    let t = 6000;
    const ep = p.lines.flatMap((l) => l.text.split(/\s+/).map((word) => { const w = { word, start_ms: t, end_ms: t + 280 }; t += 330; return w; }).concat([]));
    const out2 = compile(rd, { episodeWords: ep });
    expect(out2.estimated).toBe(false);
    expect(out2.timing_source).toBe('measured');
    expect(out2.lines[0].start_ms).toBe(6000);
  });
});
