# HANDOVER — freaktown, 2026-09-11 (pick up here)

Owner's goal, verbatim: **the avatar flow working** — prompt ("fat monkey
hates his life") → sad monkey avatar + related minute, shareable link, dad
makes his own avatars + sets. Everything below serves that.

## Live right now (verified with curl, not assumed)

- **Show (Flask, this VPS :8090):** Studio 200, sets 200, preload serves
  bodies + audio, watch pages 200. venv: `/home/ubuntu/.venvs/freaktown`
  (flask, edge-tts, pillow, httpx, kaggle). System binaries: `espeak`,
  `ffmpeg` installed via apt.
- **Public demo tunnel:** `https://latest-practice-tile-subsidiary.trycloudflare.com`
  (quick tunnel — ROTATES on restart; pin to `trial.freak.town` via named
  tunnel + DNS when ready). Demo set: `/f/dad-demo-001` (VRM body, voice,
  share page). New: `/f/brenda-37659b` (AI-written sad-fat-monkey minute,
  BASIC monkey body — species preset added this session).
- **Edge worker:** `https://freak-town.tradesprior.workers.dev` (API +
  EpisodeRoom DO + D1/R2 bindings live). Serves a labeled placeholder page —
  NOT the show. freak.town apex untouched (Flask via tunnel elsewhere).
- **Pogtown API (Docker, this VPS :8787):** Postgres store, healthcheck +
  restart survival + attacker gate 15/15 + `npm test` 67/67 green.

## Built this session (staged, NOT committed)

- `face_profiles.py` — 8-profile detector + POG_FACE_V1 intents, no invented
  morphs. Wired into `_sniff_glb`, 3 manifest writers, preload output.
- VRM expression sniffing (`extensions.VRMC_vrm`) — default VRM now reads
  viseme/lipsync/18 morphs instead of mute. Uploaded to dad-demo-001.
- `basic_body.py` monkey preset + `FREAK_SPECIES` monkey/ape (Brenda proves it).
- `NORTHSTAR.md` (avatar doctrine), `docs/avataroptions.md`,
  `docs/vendors/{bithuman,runway}.md`, `docs/BOUNDARIES.md` (merged, not
  replaced), `docs/README.md` index, `archive/` (dormant engine moved with
  `git mv`, receipted 27-green), `edge/{package.json,package-lock.json,
  .gitignore}` (worker builds now), `validateCameraCut()` contract fix.
- Pogtown: `attack-mafia.mjs` harness fix (gate was unpassable),
  `fetch-upstreams.sh` set-u fix, `.cache/upstreams/` × 8 pulled.
- Data rescued: `/home/ubuntu/data/sft/` (13,412 SFT pairs, was in /tmp).
- Kaggle run pack: `/home/ubuntu/kaggle-walkouts/` (render.py validated
  pure-logic; 7 pilot recipes, digest cache keys).

## Blockers (each with its exact unblock)

1. **Push auth** — no credentials held. Owner: `gh auth login` on this box
   or add deploy key. Then push CP0 (pogtown) + staged freaktown work.
2. **Vault reads** — opencode token is `proxy` role; `credential get` needs
   `member`. Owner runs:
   `agent-vault vault agent set-role opencode member --vault oracle`
   `agent-vault vault agent set-role opencode member --vault main`
   Then: push Kaggle kernel, attach HF_TOKEN, pull walkout wavs.
3. **CF minute-writing on live** — needs `CLOUDFLARE_API_TOKEN` (+ account)
   in the serving env. Proven working (Brenda was written with it, env-only,
   unset after). Same pair lights up `/api/respond` for everyone.
4. **three.ws / MetaPerson bodies** — no creds anywhere (vault checked).
   BASIC + upload carry the demo until accounts exist.
5. **Burned tokens** — a GH PAT and CF/R2 keys passed through chat. Saved
   nowhere by me; owner should rotate when convenient (H2-adjacent).

## Next actions (ordered)

1. Get push auth → commit staged work (freaktown) + CP0 (pogtown).
2. Get vault grant → fire Kaggle walkout kernel → bank 7 pilots → 100-bank.
3. Set CF pair on the serving Flask env → dad-loop fully live (prompt→minute).
4. Pin tunnel to `trial.freak.town`; rename `chatgpt-right` seat (trademark).
5. Bake-off lanes (Avatar SDK free avatar first) per NORTHSTAR when accounts exist.

## Traps for the unwary

- `test_party.py` runs as script, never pytest. Avatar battery needs espeak
  (now installed). 13 contract/unit failures are missing-pip-dep env noise.
- Flask serves from venv python, not system. Tunnel dies with the box;
  quick-tunnel URL dies with the tunnel. `freaks/*` is gitignored.
- The user cares about ONE thing: the avatar flow, demoable, shareable.
  Scaffold nothing; demo everything; curl every claim.
