/**
 * Wall painter — procedural video-wall cards, zero network.
 *
 * paintWallCard(ctx, card, theme, t) is a stage-runtime WallPainter: hand it
 * to SetStage ({ wallPainter }) and every overlay.headline is drawn here in
 * the show's style. Two families:
 *   paper-sunrise  (goodnight) paper-light card, sketched sunrise, accent #F5C86B
 *   broadcast      (default-news) deep-blue broadcast card
 * Layouts: title · headline · country · numbers · close.
 * Text is fitted (shrinks, wraps, then ellipsizes) so it never clips.
 * An image is drawn only when card.image_url is set — compile() sets it only
 * for licence lanes that allow it (verbatim-ok).
 */
import type { SetThemePayloadV1 } from '@funnier/contracts';

export interface WallCardInput {
  text: string;
  kicker?: string;
  layout?: string;
  body?: string;
  figure?: string;
  credit?: string;
  image_url?: string;
}

type Ctx = CanvasRenderingContext2D;

const DEF_SERIF = "Georgia, 'C059', 'Century Schoolbook', 'DejaVu Serif', serif";

export function wrapText(ctx: Ctx, text: string, maxW: number): string[] {
  const words = text.replace(/\s+/g, ' ').trim().split(' ').filter(Boolean);
  const lines: string[] = [];
  let line = '';
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
  }
  if (line) lines.push(line);
  return lines;
}

/** Largest font size (step 2px) at which text fits maxW × maxLines; ellipsizes at minSize. */
export function fitText(ctx: Ctx, text: string, font: (px: number) => string, maxW: number, maxLines: number, maxPx: number, minPx: number): { px: number; lines: string[] } {
  for (let px = maxPx; px >= minPx; px -= 2) {
    ctx.font = font(px);
    const lines = wrapText(ctx, text, maxW);
    if (lines.length <= maxLines && lines.every((l) => ctx.measureText(l).width <= maxW)) return { px, lines };
  }
  ctx.font = font(minPx);
  let lines = wrapText(ctx, text, maxW);
  if (lines.length > maxLines) {
    lines = lines.slice(0, maxLines);
    let last = lines[maxLines - 1];
    while (last.length > 1 && ctx.measureText(`${last}…`).width > maxW) last = last.slice(0, -1).trimEnd();
    lines[maxLines - 1] = `${last}…`;
  }
  return { px: minPx, lines };
}

// deterministic jitter for sketched strokes
function rnd(seed: number) { return () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 4294967296; }; }

function sketchLine(ctx: Ctx, x0: number, y0: number, x1: number, y1: number, r: () => number, wobble = 1.6) {
  ctx.beginPath();
  const n = 8;
  for (let i = 0; i <= n; i++) {
    const u = i / n;
    const x = x0 + (x1 - x0) * u + (r() - 0.5) * wobble;
    const y = y0 + (y1 - y0) * u + (r() - 0.5) * wobble;
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  }
  ctx.stroke();
}

const images = new Map<string, HTMLImageElement | 'loading' | 'failed'>();
function cachedImage(url: string): HTMLImageElement | null {
  const got = images.get(url);
  if (got instanceof HTMLImageElement) return got;
  if (!got && typeof Image !== 'undefined') {
    images.set(url, 'loading');
    const im = new Image();
    im.crossOrigin = 'anonymous';
    im.onload = () => images.set(url, im);
    im.onerror = () => images.set(url, 'failed');
    im.src = url;
  }
  return null;
}

// ── paper-sunrise (goodnight) ──────────────────────────────────────────

function paperSunrise(ctx: Ctx, card: WallCardInput, th: SetThemePayloadV1 | null, t: number) {
  const W = ctx.canvas.width, H = ctx.canvas.height;
  const P = { paper: '#f6efe2', ink: '#2a2420', accent: '#F5C86B', accent2: '#e9a77a', ...(th?.palette ?? {}) };
  const serif = th?.fonts?.display ?? DEF_SERIF;
  const brand = (th?.brand ?? 'Goodnight News');
  const layout = card.layout ?? 'headline';
  const r = rnd(7);

  // paper
  const g = ctx.createLinearGradient(0, 0, 0, H);
  g.addColorStop(0, P.paper); g.addColorStop(0.72, P.paper); g.addColorStop(1, '#f1dcc0');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  // paper fibres
  ctx.globalAlpha = 0.05; ctx.fillStyle = P.ink;
  for (let i = 0; i < 260; i++) ctx.fillRect(r() * W, r() * H, 1 + r() * 2, 1);
  ctx.globalAlpha = 1;

  // sunrise: low sun on a sketched horizon (right side), breathing glow (very slow, no strobe)
  const sx = W * 0.82, hy = H * 0.86, sr = H * 0.2;
  const breathe = 1 + 0.03 * Math.sin((t / 22) * Math.PI * 2);
  const glowG = ctx.createRadialGradient(sx, hy, sr * 0.2, sx, hy, sr * 2.6 * breathe);
  glowG.addColorStop(0, 'rgba(245,200,107,0.55)'); glowG.addColorStop(1, 'rgba(245,200,107,0)');
  ctx.fillStyle = glowG; ctx.fillRect(0, 0, W, H);
  ctx.save();
  ctx.beginPath(); ctx.rect(0, 0, W, hy); ctx.clip();
  ctx.fillStyle = P.accent; ctx.beginPath(); ctx.arc(sx, hy, sr, Math.PI, 2 * Math.PI); ctx.fill();
  // sketched rays (pencil)
  ctx.strokeStyle = 'rgba(176,122,40,0.55)'; ctx.lineWidth = 1.6;
  const rot = t * 0.004;
  for (let i = 0; i < 11; i++) {
    const a = Math.PI + (i + 0.5) * (Math.PI / 11) + rot;
    sketchLine(ctx, sx + Math.cos(a) * sr * 1.18, hy + Math.sin(a) * sr * 1.18, sx + Math.cos(a) * sr * (1.55 + (i % 2) * 0.25), hy + Math.sin(a) * sr * (1.55 + (i % 2) * 0.25), r, 1.2);
  }
  ctx.restore();
  // horizon + hatching
  ctx.strokeStyle = 'rgba(42,36,32,0.55)'; ctx.lineWidth = 1.8;
  sketchLine(ctx, 24, hy, W - 24, hy, r, 1.4);
  ctx.strokeStyle = 'rgba(42,36,32,0.18)'; ctx.lineWidth = 1;
  for (let i = 0; i < 24; i++) { const x = 40 + i * ((W - 80) / 24); sketchLine(ctx, x, hy + 10, x + 26, hy + 34, r, 1); }
  // frame rule
  ctx.strokeStyle = P.accent; ctx.lineWidth = 6; ctx.strokeRect(14, 14, W - 28, H - 28);

  const left = 64, maxW = W * 0.62;
  const kickerFont = (px: number) => `600 ${px}px ${serif}`;
  const drawKicker = (k: string, y: number) => {
    ctx.font = kickerFont(26); ctx.fillStyle = '#9a6a1c';
    const s = k.toUpperCase().split('').join('\u200A');
    ctx.fillText(s, left, y);
    const w = Math.min(maxW, ctx.measureText(s).width);
    ctx.fillStyle = P.accent; ctx.fillRect(left, y + 12, Math.max(60, w * 0.5), 4);
  };
  const credit = () => {
    if (card.credit) { ctx.font = `italic 22px ${serif}`; ctx.fillStyle = 'rgba(42,36,32,0.72)'; ctx.fillText(fitOne(ctx, `via ${card.credit}`, maxW), left, H - 44); }
  };
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = P.ink;

  if (layout === 'ambient') return; // paper + sunrise only (the wall behind a one-shot)
  if (layout === 'title' || layout === 'close') {
    const f = fitText(ctx, card.text, (px) => `600 ${px}px ${serif}`, maxW, 2, 84, 40);
    let y = H * 0.42 - ((f.lines.length - 1) * f.px * 1.12) / 2;
    if (card.kicker) drawKicker(card.kicker, y - f.px - 18);
    ctx.fillStyle = P.ink; ctx.font = `600 ${f.px}px ${serif}`;
    for (const l of f.lines) { ctx.fillText(l, left, y); y += f.px * 1.12; }
    if (card.body) { const b = fitText(ctx, card.body, (px) => `italic ${px}px ${serif}`, maxW, 2, 32, 22); ctx.fillStyle = 'rgba(42,36,32,0.8)'; ctx.font = `italic ${b.px}px ${serif}`; y += 6; for (const l of b.lines) { ctx.fillText(l, left, y); y += b.px * 1.25; } }
    ctx.font = `600 20px ${serif}`; ctx.fillStyle = 'rgba(42,36,32,0.55)';
    return;
  }
  if (layout === 'numbers') {
    drawKicker(card.kicker ?? 'The numbers', 92);
    const fig = card.figure ?? '';
    const f = fitText(ctx, fig, (px) => `700 ${px}px ${serif}`, maxW, 1, 168, 60);
    ctx.fillStyle = P.ink; ctx.font = `700 ${f.px}px ${serif}`;
    const figY = 120 + f.px * 0.92;
    ctx.fillText(f.lines[0] ?? '', left, figY);
    ctx.fillStyle = P.accent; ctx.fillRect(left, figY + 18, Math.min(maxW, ctx.measureText(f.lines[0] ?? '').width), 6);
    const lab = fitText(ctx, card.text, (px) => `${px}px ${serif}`, maxW, 2, 40, 24);
    ctx.fillStyle = P.ink; ctx.font = `${lab.px}px ${serif}`;
    let y = figY + 30 + lab.px * 1.1;
    for (const l of lab.lines) { if (y > H - 80) break; ctx.fillText(l, left, y); y += lab.px * 1.2; }
    credit();
    return;
  }
  if (layout === 'country') {
    drawKicker(card.kicker ?? 'From', 110);
    const f = fitText(ctx, card.text, (px) => `600 ${px}px ${serif}`, maxW, 1, 110, 48);
    ctx.fillStyle = P.ink; ctx.font = `600 ${f.px}px ${serif}`;
    const y = 150 + f.px * 0.9;
    ctx.fillText(f.lines[0] ?? '', left, y);
    if (card.body) { const b = fitText(ctx, card.body, (px) => `italic ${px}px ${serif}`, maxW, 1, 36, 22); ctx.font = `italic ${b.px}px ${serif}`; ctx.fillStyle = 'rgba(42,36,32,0.8)'; ctx.fillText(b.lines[0] ?? '', left, y + 24 + b.px); }
    credit();
    return;
  }
  // headline (default)
  let top = 96;
  if (card.kicker) { drawKicker(card.kicker, top); top += 40; }
  const img = card.image_url ? cachedImage(card.image_url) : null;
  const textW = img ? W * 0.5 : maxW;
  const f = fitText(ctx, card.text, (px) => `600 ${px}px ${serif}`, textW, 3, 64, 30);
  ctx.fillStyle = P.ink; ctx.font = `600 ${f.px}px ${serif}`;
  let y = top + f.px * 1.05;
  for (const l of f.lines) { ctx.fillText(l, left, y); y += f.px * 1.18; }
  if (card.body) {
    const b = fitText(ctx, card.body, (px) => `italic ${px}px ${serif}`, textW, 2, 30, 20);
    ctx.font = `italic ${b.px}px ${serif}`; ctx.fillStyle = 'rgba(42,36,32,0.78)';
    y += 4;
    for (const l of b.lines) { if (y > H - 80) break; ctx.fillText(l, left, y); y += b.px * 1.25; }
  }
  if (img) {
    const bw = W * 0.3, bh = H * 0.46, bx = W - bw - 56, by = 90;
    ctx.save(); ctx.beginPath(); ctx.rect(bx, by, bw, bh); ctx.clip();
    const s = Math.max(bw / img.width, bh / img.height);
    ctx.drawImage(img, bx + (bw - img.width * s) / 2, by + (bh - img.height * s) / 2, img.width * s, img.height * s);
    ctx.restore(); ctx.strokeStyle = P.ink; ctx.lineWidth = 2; ctx.strokeRect(bx, by, bw, bh);
  }
  credit();
}

function fitOne(ctx: Ctx, s: string, maxW: number): string {
  if (ctx.measureText(s).width <= maxW) return s;
  let x = s;
  while (x.length > 1 && ctx.measureText(`${x}…`).width > maxW) x = x.slice(0, -1);
  return `${x}…`;
}

// ── broadcast (default-news) ──────────────────────────────────────────

function broadcast(ctx: Ctx, card: WallCardInput, th: SetThemePayloadV1 | null, t: number) {
  const W = ctx.canvas.width, H = ctx.canvas.height;
  const P = { bg: '#04070f', paper: '#ffffff', accent: '#ffcc33', accent2: '#e8112d', muted: '#0c3a8c', ...(th?.palette ?? {}) };
  const sans = th?.fonts?.display ?? "Inter, Arial, 'DejaVu Sans', sans-serif";
  const g = ctx.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, '#071a3d'); g.addColorStop(0.6, P.muted); g.addColorStop(1, '#03122b');
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.globalAlpha = 0.12; ctx.fillStyle = '#7fb2ff';
  for (let i = 0; i < 14; i++) ctx.fillRect(((i * 97 + t * 40) % (W + 200)) - 200, (i * 53) % H, 180, 3);
  ctx.globalAlpha = 1;
  const layout = card.layout ?? 'headline';
  const maxW = W - 110;
  if (layout === 'ambient') return; // the wall behind a one-shot: background only
  ctx.fillStyle = P.accent2; ctx.fillRect(48, 54, 10, 46);
  ctx.fillStyle = P.accent; ctx.font = `bold 34px ${sans}`;
  ctx.fillText(fitOne(ctx, (card.kicker ?? (layout === 'numbers' ? 'The numbers' : 'News')).toUpperCase(), maxW - 40), 76, 90);
  if (layout === 'numbers') {
    const f = fitText(ctx, card.figure ?? '', (px) => `900 ${px}px ${sans}`, maxW, 1, 170, 60);
    ctx.fillStyle = '#fff'; ctx.font = `900 ${f.px}px ${sans}`; ctx.fillText(f.lines[0] ?? '', 52, 130 + f.px * 0.9);
    const lab = fitText(ctx, card.text, (px) => `bold ${px}px ${sans}`, maxW, 2, 40, 24);
    ctx.font = `bold ${lab.px}px ${sans}`; let y = 170 + f.px; for (const l of lab.lines) { ctx.fillText(l, 52, y); y += lab.px * 1.2; }
  } else {
    const f = fitText(ctx, card.text, (px) => `bold ${px}px ${sans}`, maxW, layout === 'country' ? 1 : 3, layout === 'country' ? 110 : 64, 30);
    ctx.fillStyle = '#fff'; ctx.font = `bold ${f.px}px ${sans}`;
    let y = 150 + f.px;
    for (const l of f.lines) { ctx.fillText(l, 52, y); y += f.px * 1.2; }
    if (card.body) { const b = fitText(ctx, card.body, (px) => `${px}px ${sans}`, maxW, 2, 32, 20); ctx.font = `${b.px}px ${sans}`; ctx.fillStyle = 'rgba(255,255,255,0.85)'; for (const l of b.lines) { ctx.fillText(l, 52, y); y += b.px * 1.25; } }
  }
  ctx.fillStyle = 'rgba(255,255,255,0.75)'; ctx.font = `bold 26px ${sans}`;
  ctx.fillText(fitOne(ctx, [(th?.brand ?? 'FREAK NEWS').toUpperCase(), card.credit ? `· ${card.credit}` : ''].join(' '), maxW), 52, H - 40);
}

/** The WallPainter: pick the family from the theme (goodnight → paper-sunrise). */
export function paintWallCard(ctx: Ctx, card: WallCardInput, theme: SetThemePayloadV1 | null, t: number): void {
  ctx.save();
  try {
    const family = theme?.wall?.family ?? (theme?.overlay?.lowerThird === 'paper' ? 'paper-sunrise' : 'broadcast');
    if (family === 'paper-sunrise') paperSunrise(ctx, card, theme, t);
    else broadcast(ctx, card, theme, t);
  } finally { ctx.restore(); }
}
