#!/usr/bin/env node
/**
 * newsroom-cards — paint the web stage's own wall cards (and the desk brand band) to PNGs for Blender renders.
 *
 * The Blender newsroom leaves news_wall_screen / news_desk_brand blank; the web stage paints them with
 * @funnier/newsroom's paintWallCard. For a Blender render we want the SAME pixels, so this bundles wall.ts with
 * esbuild, runs it in headless Chromium on a 1024 x 512 canvas (the stage's wall texture size) and saves PNGs.
 *
 *   node sets/blender/newsroom_cards.mjs <timeline.json> --from 15440 --to 25440 -o out/cards
 *        writes card_<k>.png for every distinct overlay.headline active in [from, to), brand.png, and
 *        cards.json: [{ "t_ms": .., "file": "card_0.png", "text": .., "layout": .. }] (t relative to --from)
 *   node sets/blender/newsroom_cards.mjs --card '{"text":"Goodnight News","layout":"title"}' --style goodnight -o out/cards
 *
 * Env: CHROMIUM_PATH (system Chromium; linux-arm64 has no Playwright-managed one).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../..');

const argv = process.argv.slice(2);
const opt = { _: [] };
for (let i = 0; i < argv.length; i++) {
  const k = argv[i];
  if (k === '-o') opt.out = argv[++i];
  else if (k.startsWith('--')) opt[k.slice(2)] = argv[++i];
  else opt._.push(k);
}
const outDir = path.resolve(opt.out ?? 'cards');
fs.mkdirSync(outDir, { recursive: true });

// 1) cards to paint
let theme = null;
const cards = [];
if (opt._[0]) {
  const tl = JSON.parse(fs.readFileSync(opt._[0], 'utf8'));
  const from = Number(opt.from ?? 0), to = Number(opt.to ?? tl.duration_ms);
  let active = null;
  for (const e of tl.events) {
    if (e.type === 'set.theme') theme = e.payload;
    if (e.type !== 'overlay.headline') continue;
    const p = e.payload;
    const card = { text: p.text, kicker: p.kicker, layout: p.layout, body: p.body, figure: p.figure, credit: p.credit };
    if (e.t_ms < from) { active = card; continue; }
    if (e.t_ms >= to) break;
    if (active && e.t_ms > from && !cards.length) cards.push({ t_ms: 0, card: active });
    cards.push({ t_ms: e.t_ms - from, card });
    active = card;
  }
  if (!cards.length && active) cards.push({ t_ms: 0, card: active });
} else if (opt.card) {
  cards.push({ t_ms: 0, card: JSON.parse(opt.card) });
}
if (!theme && (opt.style ?? 'goodnight') === 'goodnight') {
  theme = { style: 'goodnight', brand: 'Goodnight News', palette: { bg: '#07060a', paper: '#f6efe2', ink: '#2a2420', accent: '#F5C86B', accent2: '#e9a77a', muted: '#1a1612', glow: '#3a2a12' }, overlay: { lowerThird: 'paper' } };
}
// collapse consecutive duplicates (the timeline re-sends a card when a line starts)
const uniq = [];
for (const c of cards) {
  const key = JSON.stringify(c.card);
  if (uniq.length && JSON.stringify(uniq[uniq.length - 1].card) === key) continue;
  uniq.push(c);
}

// 2) bundle the painter
const { build } = await import('esbuild');
const bundle = await build({
  entryPoints: [path.join(repo, 'packages/newsroom/src/wall.ts')], bundle: true, write: false, format: 'iife',
  globalName: 'NewsWall', platform: 'browser', logLevel: 'silent',
});
const js = bundle.outputFiles[0].text;

// 3) paint in Chromium
const { chromium } = await import('@playwright/test');
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.setContent('<html><body style="margin:0"></body></html>');
await page.addScriptTag({ content: js });
const manifest = [];
for (let k = 0; k < uniq.length; k++) {
  const { t_ms, card } = uniq[k];
  const url = await page.evaluate(({ card, theme, t }) => {
    const c = document.createElement('canvas'); c.width = 1024; c.height = 512;
    // eslint-disable-next-line no-undef
    NewsWall.paintWallCard(c.getContext('2d'), card, theme, t);
    return c.toDataURL('image/png');
  }, { card, theme, t: (Number(opt.from ?? 0) + t_ms) / 1000 });
  const file = `card_${k}.png`;
  fs.writeFileSync(path.join(outDir, file), Buffer.from(url.split(',')[1], 'base64'));
  manifest.push({ t_ms, file, text: card.text, layout: card.layout ?? 'headline' });
}
// desk brand band: the same gradient + serif brand the three.js desk front paints for set.theme
const P = theme?.palette ?? {};
const brandUrl = await page.evaluate(({ a, b, ink, rule, brand, font }) => {
  const c = document.createElement('canvas'); c.width = 1024; c.height = 256;
  const x = c.getContext('2d');
  const g = x.createLinearGradient(0, 0, 1024, 0); g.addColorStop(0, a); g.addColorStop(0.5, b); g.addColorStop(1, a);
  x.fillStyle = g; x.fillRect(0, 0, 1024, 256); x.fillStyle = ink; x.font = font; x.textAlign = 'center'; x.fillText(brand, 512, 160);
  x.fillStyle = rule; x.fillRect(0, 222, 1024, 10);
  return c.toDataURL('image/png');
}, { a: P.bg ?? '#0a2a6a', b: P.muted ?? '#1960e0', ink: P.paper ?? '#fff', rule: P.accent ?? '#ffcc33', brand: (theme?.brand ?? 'FUNNIER NEWS').toUpperCase(), font: `600 84px ${theme?.fonts?.display ?? 'Georgia, serif'}` });
fs.writeFileSync(path.join(outDir, 'brand.png'), Buffer.from(brandUrl.split(',')[1], 'base64'));
fs.writeFileSync(path.join(outDir, 'cards.json'), JSON.stringify(manifest, null, 1));
await browser.close();
console.log(`[cards] ${manifest.length} card(s) + brand.png -> ${outDir}`);
for (const m of manifest) console.log(`  ${m.t_ms} ms  ${m.file}  [${m.layout}] ${m.text}`);
