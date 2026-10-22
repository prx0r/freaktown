# Funnier skin for FUNNIER (/perform, /party)

Branch `funnier-skin`. FUNNIER's public pages under www.funnier.si now look like Funnier: dark, red accents,
Anton + Inter Tight, the Funnier header (wordmark linking to https://www.funnier.si/, FUNNIER nav, round
account icon). It also adds a privacy gate on the public bill.

## What changed

| File | What |
|---|---|
| `funnier_skin.py` | New. Response layer: reskins every HTML page on `/perform*`, `/play`, `/party*`, `/join/*`, and gates the bill (`listed` flag). CLI to list/unlist acts. |
| `app.py` | Three lines at the bottom (before `__main__`): `import funnier_skin; funnier_skin.init(app)`. Nothing else. |
| `test_funnier_skin.py` | New. 40 checks: listing rules, 404s, bill filter, every mode card and JS id/class kept on stage/controller/join, JSON/PNG/SSE untouched. |
| `edge/perform-worker/` | Source of the live `freaktown-perform` Cloudflare Worker: privacy filter + the JS port of the skin (`funnier-skin.js`), see below. |
| `docs/funnier-skin/*.png` | Before/after screenshots. |

### Why a response layer and not template edits
The box runs commits that are not on GitHub (build `3acedc6`: stone-face, poker, the `/perform` bill, the
`/api/perform/*` live-room endpoints). Editing templates on top of GitHub `main` would conflict with those, and
couldn't touch the box-only pages at all. `funnier_skin` rewrites the HTML on the way out instead, so it reskins
whatever the box serves and merges with a 3-line change to `app.py`.

What the layer does to an HTML response:
1. Palette: FUNNIER pink `#ff2fa8` → Funnier red `#e8102e`, cyan `#00d4ff` → gold `#f5c76b`, the greys/blacks
   → Funnier panel/line tokens, `font-family:monospace` → Inter Tight. This applies to inline styles, `<style>` blocks
   and colour strings in scripts, so canvas/JS-built UI follows.
2. Links `https://www.funnier.si/theme.css` (shared Funnier tokens + `fn-*` components) plus a small local sheet.
3. Inserts the Funnier header at the top of `<body>`.
4. `/play` and `/party`: the mode cards become two Funnier rails (Party games, Quip Clash decks) of poster cards
   with a red CREATE + HOST button. `/perform`: the bill becomes a poster grid (monogram posters when an act has
   no portrait, gold HEADLINER tag on the first card).

Ids, classes, `data-*` attributes, inline handlers and scripts are not touched (the test checks this against the
raw templates). JSON, images, audio and the SSE `/party/<code>/stream` pass through untouched.
Kill switch: `FUNNIER_SKIN=0` turns off the reskin. The privacy gate stays on.

## Privacy: the public bill

An act appears on `/perform` only when its `freaks/<slug>/meta.json` has `"listed": true` (or `"public": true`),
and test acts never do (slug or name matching e2e / test / smoke / qa, or `"test": true`). For an unlisted act:
- its cards and links (`/perform/…`, `/f/…`, `/w/…`) are stripped from every `/perform` page, and the act count is fixed;
- `/perform/<slug>` returns 404.

**Default is hidden.** After deploying, the bill is empty until you list acts.

```
python3 funnier_skin.py status          # every bundle: LISTED/hidden, test flag
python3 funnier_skin.py list SLUG...    # put on the bill
python3 funnier_skin.py unlist SLUG...  # take off
```

The 11 acts the edge filter currently shows (not family, not tests). List them if you want the bill unchanged:

```
python3 funnier_skin.py list priscilla-ac497a thomas-bridge-ba74bd thomas-b666cf gerald-8994fb \
  archibald-archie-feathersworth-i-00aa26 priscilla-8824c7 lexi-printeon-0a6f6d inkworthy-8f37d3 \
  thomas-7162b3 thomas-09eb4f biscuit-4cb995
```

Not listed, so hidden: family sets `cathy-prior-f3ac25`, `cathy-prior-da4460`, `lara-prior-349b25`,
`lara-prior-a994e4`, `chris-prior-72abda`. Test acts: `e2e-bot-6e8a37`, `e2e-bot-32b30d`, `e2e-bot-274e9a`,
`share-test-6e2df5`, `test-face-basic-001`.

### Still public after this (not covered by the bill gate)
- `party.funnier.si/f/<slug>`, `/w/<slug>`, `/@<char>` pages and `/api/sets`, `/api/takes` still serve every
  bundle, family ones included, to anyone who goes straight to the box (`party.funnier.si` is DNS-only, so no
  Cloudflare Worker can sit in front of it). To take the family sets fully offline, move their `freaks/<slug>`
  dirs out of `freaks/` (or delete them).
- `/icon-512.png` and `/icon-192.png` on www.funnier.si are now served from the box by the `funnier-web` Worker
  (cached a day), so the act page's entrance image loads; the bill still shows monogram posters for acts without a portrait.

## Live now: the skin at the Cloudflare edge (no box deploy needed)

Since 2026-10-18 the skin runs in the two Workers in front of the box, so www.funnier.si already looks like this
branch even though the box still runs `3acedc6`:

| Worker | Routes | Source | Does |
|---|---|---|---|
| `freaktown-perform` | `www.funnier.si/perform*` | `edge/perform-worker/` (this repo) | privacy filter (below) + skin on every `/perform` HTML page; links to box-only pages (`/@char`, `/f/`, `/w/`, `/r/`, `/ar/`, `/record/`, `/edit`, `/takes`) rewritten to `https://party.funnier.si/…` (they 404 on www) |
| `funnier-web` | `www.funnier.si`, `funnier.si` | prx0r/characters `funnier/web-worker/` | party proxy (`/party`, `/party/*`, `/play`, `/join/*`) + skin on its HTML; `/icon-512.png`, `/icon-192.png` from the box |

`edge/perform-worker/funnier-skin.js` is the canonical JS port of `reskin()` (same regexes, same `SKIN_CSS`); it is
copied verbatim into the characters repo. On the live box pages (bill, act, /party, lab, join, controller, stage)
its output is byte-identical to `funnier_skin.reskin()` run with the edge's hidden-slug rule. Only `GET` `text/html`
responses are buffered and rewritten; JSON, images, audio, the SSE `/party/<code>/stream`, POSTs and HEADs pass
through as the original streaming response. `?skin=0` on any URL returns the unskinned page (privacy filter still on).
Response header `x-funnier-skin: edge` marks a skinned page. If you change `SKIN_CSS`, change both files.

Two edge-only fixes the box should also get:
- **Stage script SyntaxError** (party.py, stage template, also on main): the deck buttons are built with
  `onclick=\"hostCmd('start','quip-"+d+"')\"` inside a normal Python string, so the `\"` collapses to `"` and the
  whole stage `<script>` fails to parse (no polling, no host buttons). `funnier-web` re-escapes it on the way out.
  Fix on the box: make that template a raw string or write `\\"`.
- **Browser caching of live room state**: the zone's 4 h browser-cache TTL was being stamped on `/party/<code>/view`
  and `/stream?once=1` responses (JSON without cache-control), which can freeze controllers/stages. `funnier-web`
  now fetches the box with `cache: 'no-store'` and sends `cache-control: no-store` on everything but images.

Privacy filter (`freaktown-perform`, until the box runs the `listed` flag): slugs matching `(^|-)(prior|e2e|test)(-|$)`
are stripped from every `/perform` HTML page (cards and `/perform|f|w/<slug>` links, act count fixed) and their
`/perform/<slug>` pages return a skinned 404. That is the 10 acts listed above as hidden.

After the box merge nothing at the edge has to change: a page that already carries `<style id='funnier-skin'>`
(skinned by the box) is passed through without a second reskin (`x-funnier-skin: box`); the privacy filter keeps
running as a second line of defence.

Deploy (from a copy; the token is the vault's Cloudflare token in `CLOUDFLARE_API_TOKEN`):
```
cp -r edge/perform-worker /tmp/pw && cd /tmp/pw && CLOUDFLARE_ACCOUNT_ID=954612afb5a97bb15dddcdc70176813d npx wrangler deploy
```
Live screenshots (headless Chromium, Google Fonts served from a local copy): `docs/funnier-skin/edge/`.

## Deploy on the box (party.funnier.si, 138.199.223.35)

The box's checkout is ahead of GitHub (`/api/health` reports build `3acedc6`, which is not on origin), so
**merge the branch. Don't reset to it.**

```
ssh root@138.199.223.35
cd /root/freaktown
git status                      # commit any uncommitted work first: git add -A && git commit -m "box state"
git fetch origin
git merge origin/funnier-skin   # only app.py's last lines + new files; conflicts are unlikely
python3 test_funnier_skin.py && python3 test_party.py
python3 funnier_skin.py status
python3 funnier_skin.py list <the slugs you want on the bill>   # see the list above
systemctl restart funnier
git push origin HEAD:main       # optional: finally publish the box's commits + the skin to GitHub
```

If the box's `/perform` routes are in a module registered after `funnier_skin.init(app)`, move the
`funnier_skin.init(app)` line to after that registration. It must come after every route. Without a `/perform`
route, the skin adds its own bill (same markup) plus `/perform/<slug>` → the watch page.

Check after the restart:
```
curl -s -o /dev/null -w "%{http_code}\n" https://www.funnier.si/perform                      # 200
curl -s -o /dev/null -w "%{http_code}\n" https://www.funnier.si/perform/cathy-prior-f3ac25   # 404
curl -s https://www.funnier.si/perform | grep -c "theme.css"                                 # 1
curl -s -o /dev/null -w "%{http_code}\n" https://www.funnier.si/party                        # 200
```

Rollback: `FUNNIER_SKIN=0` in the unit's Environment (reskin off, privacy stays on), or `git revert` the merge.

## Screenshots (`docs/funnier-skin/`)
`before-*` = GitHub main or the live box (through the edge filter); `after-*` = this branch.
`play`, `perform` (live box bill reskinned), `perform-local-fallback` (branch's own bill: listed acts only),
`act` / `act-stage` (an act page, entrance overlay and stage), `join`, `controller`, `stage`, `lab`.
