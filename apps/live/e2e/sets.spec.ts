/**
 * Sets e2e — /control drives /stage through the LocalTransport for each set:
 * the set loads (procedural, zero downloads), its demo runs, ≥2 camera cuts,
 * no console errors; poker: a human takes /play/:ep/seat/4 and acts, and the
 * stage reflects it through to showdown. Screenshots (wide + close) desktop
 * 1440×900 and mobile 390×844 → $SHOTS_DIR/sets.
 * Headless: ?quality=low&cpuskin=1 (SwiftShader, see live-stage.spec.ts).
 */
import { test, expect, type Page, type ConsoleMessage, type BrowserContext } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SHOTS = path.join(process.env.SHOTS_DIR || '/workspace/work/freaktown-live/shots', 'sets');
fs.mkdirSync(SHOTS, { recursive: true });
const Q = 'quality=low&cpuskin=1';

type SetTele = {
  setId: string | null; camera: string; cuts: Array<{ cue: string; source: string }>; lines: number;
  seats: Array<{ seat: string; name: string; avatar: string; speaking: boolean; mouth: number; seated: boolean; emotions: Record<string, number>; faceSources: string[] }>;
  overlay: { lowerThird: unknown; ticker: string[]; headline: { text: string } | null; speaker: unknown };
  poker: null | { history: Array<{ seat: number }>; handId: string; pot: number; board: unknown[]; lastAction: { seat: number; action: string } | null; winners: Array<{ seat: number }>; names: Record<number, string> };
  props: null | { hole: number; board: number; pot: number };
  environment: string;
};

function watch(page: Page, name: string, sink: string[]): void {
  page.on('console', (m: ConsoleMessage) => { if (m.type() === 'error') sink.push(`${name}: ${m.text()}`); });
  page.on('pageerror', (e) => sink.push(`${name} pageerror: ${e.message}`));
}
const tele = (stage: Page) => stage.evaluate(() => window.__setStage?.telemetry() as unknown as SetTele | undefined);

async function open(context: BrowserContext, ep: string, errors: string[]) {
  const control = await context.newPage();
  watch(control, 'control', errors);
  await control.goto(`/control/${ep}`);
  await expect(control.getByTestId('link-status')).toContainText('connected');
  await control.getByTestId('reset').click();
  const stage = await context.newPage();
  watch(stage, 'stage', errors);
  await stage.goto(`/stage/${ep}?${Q}`);
  await stage.waitForFunction(() => !!window.__stage); // classic club stage before any set.load
  return { control, stage };
}

async function runDemo(control: Page, stage: Page, setId: string) {
  await control.bringToFront();
  await control.getByTestId('set-picker').selectOption(setId);
  await control.getByTestId('set-demo').click();
  await stage.bringToFront();
  await stage.waitForFunction((id) => window.__setStage?.telemetry().setId === id, setId, { timeout: 90_000 });
}

async function shots(control: Page, stage: Page, setId: string, wide: string, close: string) {
  for (const [vp, tag] of [[{ width: 1440, height: 900 }, 'desktop'], [{ width: 390, height: 844 }, 'mobile']] as const) {
    await stage.setViewportSize(vp);
    for (const [cue, kind] of [[wide, 'wide'], [close, 'close']] as const) {
      await control.bringToFront();
      const btn = control.getByTestId(`setcam-${cue}`);
      if (await btn.count()) await btn.click();
      else await control.getByRole('button', { name: cue, exact: true }).click();
      await stage.bringToFront();
      await stage.waitForFunction((c) => window.__setStage?.telemetry().camera === c, cue);
      await stage.waitForTimeout(700);
      await stage.screenshot({ path: path.join(SHOTS, `${setId}_${kind}_${tag}.png`) });
    }
  }
  await stage.setViewportSize({ width: 1440, height: 900 });
}

test.describe.configure({ mode: 'serial' });

test('news studio: anchors read 3 headlines with ticker + lower third, ≥2 cuts', async ({ context }) => {
  const errors: string[] = [];
  const { control, stage } = await open(context, 'sets-news', errors);
  await runDemo(control, stage, 'news-studio');
  await stage.waitForFunction(() => (window.__setStage!.telemetry().overlay.headline?.text ?? '').includes('pie'), null, { timeout: 30_000 });
  await expect(stage.getByTestId('ticker')).toBeVisible();
  await expect(stage.getByTestId('lower-third')).toBeVisible();
  let t = (await tele(stage))!;
  expect(t.seats.map((s) => s.seat).sort()).toEqual(['anchor1', 'anchor2']);
  expect(t.seats.every((s) => s.seated)).toBe(true);
  // mouth moves on the speaking anchor
  await stage.waitForFunction(() => window.__setStage!.telemetry().seats.some((s) => s.speaking && s.mouth > 0.2), null, { timeout: 20_000 });
  await stage.waitForFunction(() => (window.__setStage!.telemetry().overlay.headline?.text ?? '').includes('puns'), null, { timeout: 40_000 });
  t = (await tele(stage))!;
  expect(new Set(t.cuts.map((c) => c.cue)).size).toBeGreaterThanOrEqual(3);
  await shots(control, stage, 'news-studio', 'wide', 'anchor1-single');
  expect(errors).toEqual([]);
});

test('podcast: 3 characters trade lines with active-speaker auto cuts', async ({ context }) => {
  const errors: string[] = [];
  const { control, stage } = await open(context, 'sets-pod', errors);
  await runDemo(control, stage, 'podcast');
  await stage.waitForFunction(() => window.__setStage!.telemetry().lines >= 5, null, { timeout: 60_000 });
  const t = (await tele(stage))!;
  expect(t.seats).toHaveLength(3);
  const auto = t.cuts.filter((c) => c.source === 'auto_director').map((c) => c.cue);
  expect(auto.length).toBeGreaterThanOrEqual(2);
  expect(auto.some((c) => /seat1/.test(c))).toBe(true);
  expect(auto.some((c) => /seat2|seat3/.test(c))).toBe(true);
  await expect(stage.getByTestId('on-air')).toBeVisible();
  // face: set-driven emotion cue + live ARKit stream reach the seat's face channel
  await control.bringToFront();
  await control.getByTestId('face-seat').selectOption('seat2');
  await control.getByTestId('face-surprised').click();
  await stage.bringToFront();
  await stage.waitForFunction(() => (window.__setStage!.telemetry().seats.find((s) => s.seat === 'seat2')?.emotions.surprised ?? 0) > 0.4, null, { timeout: 15_000 });
  await control.bringToFront();
  await control.getByTestId('face-puppet').click();
  await stage.bringToFront();
  await stage.waitForFunction(() => window.__setStage!.telemetry().seats.find((s) => s.seat === 'seat2')?.faceSources.includes('live'), null, { timeout: 15_000 });
  await shots(control, stage, 'podcast', 'wide', 'seat2-single');
  expect(errors).toEqual([]);
});

test('poker: 5 bots + a human from /play play a hand to showdown; stage reflects the human', async ({ context }) => {
  test.setTimeout(300_000);
  const errors: string[] = [];
  const { control, stage } = await open(context, 'sets-poker', errors);
  await runDemo(control, stage, 'poker-table');
  const play = await context.newPage();
  watch(play, 'play', errors);
  await play.setViewportSize({ width: 390, height: 844 });
  await play.goto('/play/sets-poker/seat/4');
  await play.getByTestId('play-name').fill('Tester');
  await play.getByTestId('play-join').click();
  await expect(play.getByTestId('play-joined')).toContainText('Tester');
  await stage.bringToFront();
  await stage.waitForFunction(() => window.__setStage!.telemetry().seats.some((s) => s.seat === 'seat4' && s.name === 'Tester'), null, { timeout: 20_000 });
  await stage.waitForFunction(() => !!window.__setStage!.telemetry().poker?.handId && (window.__setStage!.telemetry().props?.hole ?? 0) >= 2, null, { timeout: 30_000 });
  await expect(play.locator('[data-testid=play-cards] span')).toHaveCount(2, { timeout: 20_000 });
  let humanActs = 0;
  const deadline = Date.now() + 200_000;
  while (Date.now() < deadline) {
    if (await play.getByTestId('play-result').count()) break;
    if (await play.getByTestId('play-turn').count()) {
      const check = play.getByTestId('act-check');
      if (await check.count()) await check.click(); else await play.getByTestId('act-call').click();
      humanActs++;
      const n = humanActs;
      await stage.bringToFront();
      const ok = await stage.waitForFunction((k) => (window.__setStage!.telemetry().poker as any)?.history.filter((h: { seat: number }) => h.seat === 4).length >= k, n, { timeout: 20_000 }).then(() => true, () => false);
      if (!ok) throw new Error(`stage never showed the human action; control says: ${await control.getByTestId('sets-status').textContent()} · executed ${await stage.evaluate(() => JSON.stringify([window.__setStage!.executor.executed.map((e) => e.seq).join(','), window.__setStage!.errors, (window.__setStage as any).consumer.lastSeq]))} · log ${await stage.evaluate(() => JSON.parse(localStorage.getItem('ft-live:sets-poker:log') || '[]').filter((e: any) => !/deal|chips/.test(e.type)).map((e: any) => `${e.seq}:${e.type}:${e.payload.seat ?? e.payload.cue ?? ''}:${e.payload.action ?? ''}`).join(' '))}`);
      if (humanActs === 1) {
        await stage.screenshot({ path: path.join(SHOTS, 'poker-table_human-acted_desktop.png') });
      }
    }
    await stage.bringToFront();
    await stage.waitForTimeout(500);
  }
  expect(humanActs).toBeGreaterThan(0);
  await expect(play.getByTestId('play-result')).toBeVisible({ timeout: 30_000 });
  await stage.waitForFunction(() => (window.__setStage!.telemetry().poker?.winners.length ?? 0) > 0, null, { timeout: 30_000 });
  await expect(stage.getByTestId('poker-winner')).toBeVisible();
  const t = (await tele(stage))!;
  expect(new Set(t.cuts.map((c) => c.cue)).size).toBeGreaterThanOrEqual(3);
  expect(t.poker!.names[4]).toBe('Tester');
  await play.screenshot({ path: path.join(SHOTS, 'poker-table_play_mobile.png') });
  await shots(control, stage, 'poker-table', 'wide', 'close:seat4');
  expect(errors).toEqual([]);
});

test('comedy club stays set #1: loading it returns the classic stage', async ({ context }) => {
  const errors: string[] = [];
  const { control, stage } = await open(context, 'sets-club', errors);
  await runDemo(control, stage, 'podcast');
  await control.bringToFront();
  await control.getByTestId('set-picker').selectOption('comedy-club');
  await control.getByTestId('set-load').click();
  await stage.bringToFront();
  await stage.waitForFunction(() => !window.__setStage && !!window.__stage, null, { timeout: 30_000 });
  expect(errors).toEqual([]);
});
