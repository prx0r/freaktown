// freaktown-perform: www.funnier.si/perform* -> party.funnier.si (the Freak Town box).
// Interim privacy filter (until the box runs the funnier-skin branch's `listed` flag): family members' sets and test
// acts are stripped from every /perform HTML page and their /perform/<slug> pages return 404.
const ORIGIN = 'https://party.funnier.si';
const HIDDEN = /(^|-)(prior|e2e|test)(-|$)/; // slugs: <name>-<hash>; Cathy/Lara/Chris Prior, E2E Bot, Share Test, Face Test
const hidden = (slug) => HIDDEN.test(String(slug).toLowerCase());
const notFound = () => new Response('<!doctype html><meta charset="utf-8"><title>Not found</title><body style="background:#07070a;color:#8d8b93;font:15px system-ui;text-align:center;padding:80px 16px">This act isn’t on the bill. <a style="color:#ff3d55" href="/perform">Back to tonight’s bill</a></body>', { status: 404, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store', 'x-robots-tag': 'noindex' } });

export default {
  async fetch(req) {
    const url = new URL(req.url);
    const m = url.pathname.match(/^\/perform\/([^/?#]+)/);
    if (m && hidden(decodeURIComponent(m[1]))) return notFound();
    const res = await fetch(new Request(new URL(url.pathname + url.search, ORIGIN), req));
    if (!(res.headers.get('content-type') || '').includes('text/html')) return res;
    let html = await res.text(), removed = 0;
    // drop every card/link to a hidden act (cards are <a href='/perform/<slug>' ...>…</a> with no nested anchors)
    html = html.replace(/<a\b[^>]*href=(["']?)\/(?:perform|f|w)\/([^"'?#/\s>]+)\1[^>]*>[\s\S]*?<\/a>/g, (a, q, slug) => {
      if (!hidden(slug)) return a; if (a.includes('<img')) removed++; return ''; // only bill cards carry an image
    });
    html = html.replace(/<p\b[^>]*>\s*Headliner:\s*<\/p>/, '');
    if (removed) html = html.replace(/(\d+) acts\b/, (s, n) => `${Math.max(0, +n - removed)} acts`);
    const h = new Headers(res.headers); h.delete('content-length'); h.set('cache-control', 'no-store');
    return new Response(html, { status: res.status, headers: h });
  }
};
