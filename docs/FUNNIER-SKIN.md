# Funnier skin for Freak Town (/perform, /party)

Branch `funnier-skin`. Freak Town's public pages under www.funnier.si now look like Funnier: dark, red accents,
Anton + Inter Tight, the Funnier header (wordmark linking to https://www.funnier.si/, Freak Town nav, round
account icon). It also adds a privacy gate on the public bill.

## What changed

| File | What |
|---|---|
| `funnier_skin.py` | New. Response layer: reskins every HTML page on `/perform*`, `/play`, `/party*`, `/join/*`, and gates the bill (`listed` flag). CLI to list/unlist acts. |
| `app.py` | Three lines at the bottom (before `__main__`): `import funnier_skin; funnier_skin.init(app)`. Nothing else. |
| `test_funnier_skin.py` | New. 40 checks: listing rules, 404s, bill filter, every mode card and JS id/class kept on stage/controller/join, JSON/PNG/SSE untouched. |
| `edge/perform-worker/` | Source of the live `freaktown-perform` Cloudflare Worker (interim edge filter, see below). |
| `docs/funnier-skin/*.png` | Before/after screenshots. |

### Why a response layer and not template edits
The box runs commits that are not on GitHub (build `3acedc6`: stone-face, poker, the `/perform` bill, the
`/api/perform/*` live-room endpoints). Editing templates on top of GitHub `main` would conflict with those, and
couldn't touch the box-only pages at all. `funnier_skin` rewrites the HTML on the way out instead, so it reskins
whatever the box serves and merges with a 3-line change to `app.py`.

What the layer does to an HTML response:
1. Palette: Freak Town pink `#ff2fa8` → Funnier red `#e8102e`, cyan `#00d4ff` → gold `#f5c76b`, the greys/blacks
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
- The bill's `/icon-512.png` placeholders 404 on www.funnier.si (that path goes to GitHub Pages, not the box).
  The skin swaps them for monogram posters on the bill. The act page's own fallback image still needs the path
  served from the box (add `www.funnier.si/icon-512.png` to a Worker route, or use an absolute party.funnier.si URL).

## Interim edge filter (live now)

Until the box runs this branch, the `freaktown-perform` Worker (route `www.funnier.si/perform*`, source in
`edge/perform-worker/`) strips cards and links to slugs matching `(^|-)(prior|e2e|test)(-|$)` from `/perform` HTML
and returns 404 for their `/perform/<slug>` pages. Once the branch is live and the acts are listed, set the Worker back
to a plain proxy (or keep it as a second line of defence; it does no harm):

```
cd edge/perform-worker && CLOUDFLARE_ACCOUNT_ID=954612afb5a97bb15dddcdc70176813d npx wrangler deploy
```

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
systemctl restart freaktown
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
