// freaktown-perform: www.funnier.si/perform* -> party.funnier.si (the Freak Town box).
// 1. Privacy filter (until the box runs funnier_skin.py's `listed` flag): family members' sets and test acts are
//    stripped from every /perform HTML page and their /perform/<slug> pages return 404.
// 2. Funnier skin (funnier-skin.js, a port of funnier_skin.reskin): every /perform HTML page gets the Funnier
//    theme, header and poster-grid bill. Non-HTML responses (JSON, audio, images) stream through untouched.
// 3. Links to box-only pages (/@char, /f/, /w/, /r/, /ar/, /record/, /edit, /takes) point at party.funnier.si,
//    since those paths 404 on www (GitHub Pages).
import { reskin, skinnable, skinResponse } from './funnier-skin.js';

const ORIGIN = 'https://party.funnier.si';
const HIDDEN = /(^|-)(prior|e2e|test)(-|$)/; // slugs: <name>-<hash>; Cathy/Lara/Chris Prior, E2E Bot, Share Test, Face Test
const hidden = (slug) => HIDDEN.test(String(slug).toLowerCase());
const notFound = () => new Response(reskin('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Not found · Freak Town</title></head><body style="text-align:center;padding:0 16px 80px"><h1 style="margin-top:60px">Not on the bill</h1><p style="color:#8d8b93">This act isn’t on tonight’s bill.</p><p><a style="color:#ff3d55" href="/perform">Back to tonight’s bill</a></p></body></html>', '/perform/x'), { status: 404, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex' } });

function filter(html) {
  let removed = 0;
  // drop every card/link to a hidden act (cards are <a href='/perform/<slug>' ...>…</a> with no nested anchors)
  html = html.replace(/<a\b[^>]*href=(["']?)\/(?:perform|f|w)\/([^"'?#/\s>]+)\1[^>]*>[\s\S]*?<\/a>/g, (a, q, slug) => {
    if (!hidden(slug)) return a; if (a.includes('<img')) removed++; return ''; // only bill cards carry an image
  });
  html = html.replace(/<p\b[^>]*>\s*Headliner:\s*<\/p>/, '');
  if (removed) html = html.replace(/(\d+) acts\b/, (s, n) => `${Math.max(0, +n - removed)} acts`);
  // box-only pages: absolute links to the box (www would 404)
  html = html.replace(/\bhref=(["'])\/(@|f\/|w\/|r\/|ar\/|record\/|edit\b|takes\b)/g, (s, q, p) => `href=${q}${ORIGIN}/${p}`);
  return html;
}

export default {
  async fetch(req) {
    const url = new URL(req.url);
    const m = url.pathname.match(/^\/perform\/([^/?#]+)/);
    if (m && hidden(decodeURIComponent(m[1]))) return notFound();
    const res = await fetch(new Request(new URL(url.pathname + url.search, ORIGIN), req));
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res;
    if (skinnable(req, res, url.pathname) && url.searchParams.get('skin') !== '0') return skinResponse(res, url.pathname, filter);
    // HTML we don't reskin (HEAD, 5xx, ?skin=0): privacy filter only
    const html = filter(await res.text());
    const h = new Headers(res.headers); h.delete('content-length'); h.delete('content-encoding'); h.set('cache-control', 'no-store');
    return new Response(req.method === 'HEAD' ? null : html, { status: res.status, headers: h });
  }
};
