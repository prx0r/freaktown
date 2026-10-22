# CHARACTERS MCP: the /characters3 studio for agents

An MCP server that lets an agent (Hark, Claude, ChatGPT, Codex) **create a
persistent comedy character with a deep theory of that character, then write,
revise, direct, preview and submit sets with it**, and seat it at a
Try-Not-To-Smile table. Code: `packages/characters` (`@funnier/characters`).
Browse the results at **`/characters3`** in the live app.

- Built on `packages/party`: identities come from `createIdentity()` (same GLB
  recipe with ARKit morphs, same taste model, same registry every room reads);
  sets become performances through the write-a-minute pipeline
  (`minuteToSketch`/`submitMinute`) as `funnier.sketch/v1`; delivery starts from
  `suggestDelivery`; TNTS seats use `TntsGame`/`AgentPlayer`.
- Storage is plain files in the repo (git-friendly, stable JSON).
- Generation is deterministic and template-based. The LLM hook is **off**;
  nothing calls a paid API.
- Transports: **stdio** and **streamable HTTP** (stateless, `POST /mcp`).
- The craft model behind every theory field: [CHARACTER-THEORY.md](CHARACTER-THEORY.md).

## Install

Prerequisite (once): `npm ci` in the repo root (Node 20+). The server runs
TypeScript directly through `vite-node`, which is already a dev dependency.
Replace `/ABS/freaktown` with your checkout path.

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "funnier-characters": {
      "command": "/ABS/freaktown/node_modules/.bin/vite-node",
      "args": ["/ABS/freaktown/packages/characters/bin/characters-mcp.ts"]
    }
  }
}
```

Restart Claude Desktop; the 13 tools appear under "funnier-characters".
(Claude Code: `claude mcp add funnier-characters -- /ABS/freaktown/node_modules/.bin/vite-node /ABS/freaktown/packages/characters/bin/characters-mcp.ts`.)

### Codex CLI

`~/.codex/config.toml`:

```toml
[mcp_servers.funnier-characters]
command = "/ABS/freaktown/node_modules/.bin/vite-node"
args = ["/ABS/freaktown/packages/characters/bin/characters-mcp.ts"]
# optional: write somewhere other than the repo
# env = { CHARACTERS_LIBRARY = "/tmp/my-characters" }
```

### Hark (and other remote clients, e.g. ChatGPT connectors)

Remote clients need the HTTP transport at a URL they can reach:

```bash
npm run characters:mcp:http -- --host 127.0.0.1 --port 8765
# health: curl http://127.0.0.1:8765/health
# MCP endpoint: http://127.0.0.1:8765/mcp
```

Put it behind HTTPS with access control (a tunnel or reverse proxy that
requires a token); the server itself has **no auth** and writes to the repo,
so never expose it bare. Then register the URL as an MCP server in Hark
(Settings → MCP servers, or ask Hark to "add the MCP server at
https://<host>/mcp"). Hark-style config:

```json
{ "name": "funnier-characters", "transport": "streamable-http", "url": "https://<your-host>/mcp" }
```

### Tool names

Tools are registered as `character_create`, `set_write`, … because Claude's
and OpenAI's tool-name rules (`^[a-zA-Z0-9_-]{1,64}$`) reject dots. The brief's
dotted names (`character.create`, `set.write`, …) are also registered when
`CHARACTERS_MCP_DOTTED=1`, for clients that accept them.

### Environment

| var | default | what |
|---|---|---|
| `CHARACTERS_LIBRARY` | `packages/characters/library` | theories, sets, performances, `index.json` |
| `PARTY_IDENTITIES_DIR` | `packages/party/identities` | identity records + `registry.json` |
| `CHARACTERS_GLB_DIR` | `apps/live/public/identities` | procedural GLBs |
| `CHARACTERS_SKETCH_DIR` | `apps/live/public/sketches` | submitted performances (so `/sketch/<id>` plays them) |
| `CHARACTERS_PREVIEW_DIR` | `var/characters-previews` (gitignored) | rendered MP4s |
| `CHARACTERS_MCP_DOTTED` | unset | `1` = also register dotted tool names |
| `CHROMIUM_PATH` | unset | Chromium for `set_preview render:true` |

## Tool reference

Characters are addressed by id (`agent.hark-lantern`), slug (`hark-lantern`)
or name (`Hark Lantern`). Every tool returns JSON as text; errors come back
with `isError: true` and a plain message.

| tool (dotted alias) | arguments | does |
|---|---|---|
| `character_create` (`character.create`) | `by`, and `premise` **or** `choose:true`; optional `seed`, `name`, `bio`, `catchphrase`, `delivery`, `writes[]`, `head`, `voice_id`; or `adopt:<identity id>` | Creates the identity (party `createIdentity`), the full theory, the GLB (jawOpen, mouthSmileLeft/Right, eyeBlinkLeft/Right) and registers it. `choose:true` lets the agent pick everything from original banks (seeded, reproducible). `adopt` builds a theory for an existing identity. |
| `character_get` (`character.get`) | `character`, `include_markdown?` | Identity + theory (+ rendered THEORY.md) + sets + performances. |
| `character_list` (`character.list`) | none | Every character with logline, delivery, set count, appearances. |
| `character_update_theory` (`character.update_theory`) | `character`, `patch`, `note?`, `by?`, `replace?[]` | Deep-merge a partial theory. Objects merge, arrays replace; `material`/`callbacks`/`relationships` upsert by `id`/`who` (`_delete:true` removes one) unless listed in `replace`. `null` deletes a key. Validated, changelogged, THEORY.md regenerated. |
| `set_write` (`set.write`) | `character`, `premise`, `length` (1, 3 or 5), `seed?`, `title?` | Writes a set: opener, bits (setup/punch/tag, act-outs) ordered as a game (establish → heighten → explore → top), a callback and a closer, timed to the length. Returns the script + a voice check. |
| `set_get` (`set.get`) | `set` | The set JSON + readable script. |
| `set_revise` (`set.revise`) | `set`, `notes` | Notes, one per line or `;`-separated: `cut l7`, `cut beat 3`, `replace l7: <text>`, `tag l7: <text>`, `swap beats 2 4`, `tighten`, `slower`, `faster`, `more deadpan` (any delivery), `punch up beat 3`, `add callback`. Anything else is returned as **unhandled**; nothing is guessed. |
| `set_suggest_delivery` (`set.suggest_delivery`) | `set`, `lines?[]` | Re-suggests style, pause, hold, emphasis from role + physicality. |
| `set_set_delivery` (`set.set_delivery`) | `set`, `line`, `style?`, `pause_ms?`, `hold_ms?`, `emphasis?[]` | Overrides one line. Styles: deadpan, deliberate, manic, warm, conspiratorial, pause. |
| `set_check_voice` (`set.check_voice`) | `set`, **or** `character` + `text` | Consistency checker: errors (forbidden words, taboo, safety rails), warnings (off-voice), info (craft). Score 0–1. |
| `set_preview` (`set.preview`) | `set`, `render?`, `clip_seconds?`, `event_limit?` | Stage events for the comedy-club stage (the `/sketch` timeline). `render:true` renders a short MP4 via `packages/sketch/cli/render.mjs` (needs `apps/live` built and Chromium; minutes per 30 s of video). |
| `set_submit` (`set.submit`) | `set`, `force?` | Validates and saves a `funnier.sketch/v1` performance (blocked by voice errors unless `force`), copies it to `apps/live/public/sketches/` so `/sketch/<id>` plays it, logs an appearance. |
| `game_tnts_join` (`game.tnts_join`) | `character`, `seed?`, `opponents?[]` | Seats the character at a TNTS table against resident agents (or other studio characters). Its turns use its own sets first; every smile is the party taste model (simulated, seeded). Returns table, turns, smile breaks, standings. |

A typical session:

```
character_create {by:"claude", choose:true}
character_update_theory {character, patch:{material:[...], comic_want:"..."}}
set_write {character, premise:"printers have moods and no off switch", length:3}
set_check_voice {set}
set_revise {set, notes:"cut l9; punch up beat 2; add callback"}
set_set_delivery {set, line:"l12", pause_ms:1000, emphasis:["seven"]}
set_preview {set}            # or {set, render:true, clip_seconds:20}
set_submit {set}
game_tnts_join {character}
```

## The theory model (summary)

`funnier.character-theory/v1`, JSON Schema in
`packages/characters/schemas/character-theory.v1.json`. Full rationale and
citations: [CHARACTER-THEORY.md](CHARACTER-THEORY.md).

| field | craft question |
|---|---|
| `logline`, `premise`, `intro` | who are they, what is the act |
| `comic_want`, `need` | what they chase (Kaplan "winning") vs what would actually fix them |
| `flaw.{flaw, blind_spot, misinterpretation_rule, misreads}` | the flaw (Vorhaus), what they cannot see, how criticism gets twisted |
| `status.{plays, to_audience, felt, actual, see_saw}` | Johnstone status: played vs felt, and how it tips |
| `point_of_view.{attitude, take, lens}` | comic perspective; Carter's hard/weird/scary/stupid |
| `game.{base_reality, unusual_thing, pattern, heighten, explore}` | UCB game of the character |
| `voice.*` | register, sentence shape and length, contractions, tics, signature and forbidden words, substitutions |
| `physicality.*` | default delivery (deadpan, manic, …), energy, pace, punch hold, stillness, gestures |
| `taste.*` | the party TNTS taste model + what makes them smile / stay stone-faced |
| `writes` | joke mechanisms they write in |
| `worldview.*` | ontology, epistemology, axiology, causality, agency (characters3 philosophy block) |
| `contradictions`, `backstory_anchors` | what keeps them from being one joke; concrete facts |
| `catchphrases`, `callbacks` | catchphrases and named runners that persist across sets |
| `taboo.*` | never-targets, never-topics, never-says, safety rails (checker errors) |
| `relationships` | who, dynamic, Kaplan metaphorical relationship, status |
| `humanity` | the bridge back to the audience |
| `arc.*` | flat / slow-change / circular, stages, reset rule, logged appearances |
| `material` | joke kernels (topic, attitude, premise, setups, act-outs, punch, tags, mechanism, game move, callback) the writer places first |

`toCharacters3Seed(theory)` maps a theory onto the characters3
`character.seed.v1` vocabulary (dramatic_core, misinterpretation_rule,
status_model, philosophy, threads) for graduating a character there.

## Storage

```
packages/characters/library/<slug>/theory.json      source of truth
packages/characters/library/<slug>/THEORY.md        generated theory doc
packages/characters/library/<slug>/sets/<id>.json   funnier.character-set/v1
packages/characters/library/<slug>/sets/<id>.md     readable script + revisions
packages/characters/library/<slug>/performances/<id>.sketch.json
packages/characters/library/index.json              catalog for /characters3
packages/party/identities/<id>.json, registry.json  identities (party CLI layout)
apps/live/public/identities/<id>.glb                procedural body
apps/live/public/sketches/<id>.sketch.json          submitted performances
var/characters-previews/<set>.mp4                   rendered previews (gitignored)
```

## /characters3 (live app)

`apps/live/src/pages/CharactersPage.tsx`: roster → character (theory tab:
the rendered THEORY.md; sets tab: every line with role and delivery cues, the
revision log, **Preview on stage** in the `/sketch` player, and a link to the
submitted performance). Read-only by design: writing goes through the MCP
tools, and the page reads `library/index.json`, which every write regenerates.

## Develop

```bash
npx vitest run packages/characters        # tools + MCP stdio smoke + HTTP transport
npx tsc -p packages/characters
npx vite-node packages/characters/demo/run-demo.ts     # the demo, through MCP only
RENDER=1 CHROMIUM_PATH=/path/to/chrome npx vite-node packages/characters/demo/run-demo.ts
```

The demo (`packages/characters/demo/`) recreates Hark Lantern's full theory,
writes and directs a new 3-minute set, and creates a second character by
agent choice, logging every tool call to `transcript.jsonl` and
`TRANSCRIPT.md`.

## What it does not do (yet)

- No auth on the HTTP transport (put it behind a proxy).
- The template writer is deterministic and serviceable; sharp material comes
  from authored kernels in the theory or from turning the LLM hook on
  (`setLlmHook`), which needs a spend decision.
- TNTS seats are agent-vs-agent simulations; a human joins the same table at
  `/tnts`.
- MP4 rendering is slow (headless frame capture) and needs Chromium.
