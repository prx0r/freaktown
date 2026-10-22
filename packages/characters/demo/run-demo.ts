/**
 * The demo, through the MCP tools ONLY: an MCP client spawns the stdio server
 * and makes every change with tool calls, logging each call to
 *   packages/characters/demo/transcript.jsonl   (every call, full args + full result)
 *   packages/characters/demo/TRANSCRIPT.md      (readable)
 *
 *   npx vite-node packages/characters/demo/run-demo.ts            # stage events only
 *   RENDER=1 CHROMIUM_PATH=/path/to/chrome npx vite-node packages/characters/demo/run-demo.ts
 *
 * 1. Hark Lantern: adopt the existing identity, recreate the full theory
 *    (character_update_theory), write a NEW 3-minute set, check voice, revise,
 *    tune delivery, preview, submit, join Try-Not-To-Smile.
 * 2. A second character made by character_create with choose:true (the agent
 *    chooses), given a 1-minute set and a TNTS seat.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');
const jsonl = path.join(here, 'transcript.jsonl');
const md: string[] = [];
fs.writeFileSync(jsonl, '');

const transport = new StdioClientTransport({
  command: path.join(repo, 'node_modules/.bin/vite-node'),
  args: [path.join(repo, 'packages/characters/bin/characters-mcp.ts')],
  cwd: repo,
  env: { ...process.env } as Record<string, string>,
  stderr: 'inherit',
});
const client = new Client({ name: 'characters-demo', version: '0.1.0' });
await client.connect(transport);

let n = 0;
async function call(name: string, args: Record<string, unknown>, opts: { show?: (r: any) => string; argsShown?: Record<string, unknown> } = {}): Promise<any> {
  const res = await client.callTool({ name, arguments: args }, undefined, { timeout: 30 * 60_000 });
  const text = (res.content as Array<{ type: string; text: string }>)[0]?.text ?? '';
  if (res.isError) throw new Error(`${name} failed: ${text}`);
  const out = JSON.parse(text);
  n += 1;
  fs.appendFileSync(jsonl, JSON.stringify({ n, tool: name, arguments: args, result: out }) + '\n');
  md.push(`### ${n}. \`${name}\`\n\n\`\`\`json\n${JSON.stringify(opts.argsShown ?? args, null, 1)}\n\`\`\`\n\n${opts.show ? opts.show(out) : '```json\n' + JSON.stringify(out, null, 1).slice(0, 1800) + '\n```'}\n`);
  console.error(`[demo] ${n}. ${name} ok`);
  return out;
}

const tools = await client.listTools();
md.push(`# CHARACTERS MCP demo transcript\n\nEvery change below was made through MCP tool calls over stdio (client: @modelcontextprotocol/sdk, server: \`packages/characters/bin/characters-mcp.ts\`). Full arguments and results: \`transcript.jsonl\`.\n\nServer tools (${tools.tools.length}): ${tools.tools.map((t) => `\`${t.name}\``).join(', ')}\n\n## 1. Hark Lantern\n`);

await call('character_list', {});
await call('character_create', { by: 'hark', adopt: 'agent.hark-lantern' });
const patch = JSON.parse(fs.readFileSync(path.join(here, 'hark-lantern.theory-patch.json'), 'utf8'));
await call('character_update_theory', { character: 'hark-lantern', by: 'hark', note: 'Full theory recreated from the identity, the original minute and the craft model', replace: ['material', 'callbacks', 'relationships'], patch },
  { argsShown: { character: 'hark-lantern', by: 'hark', note: '…', replace: ['material', 'callbacks', 'relationships'], patch: `(${Object.keys(patch).length} keys; see demo/hark-lantern.theory-patch.json)` } });
await call('character_get', { character: 'Hark Lantern', include_markdown: true }, { show: (r) => `Theory doc: \`packages/characters/library/hark-lantern/THEORY.md\` (${r.theory_markdown.length} chars, ${r.theory.material.length} material kernels).` });

const premise = 'users want everything at three in the morning and call it a quick question';
const w = await call('set_write', { character: 'hark-lantern', premise, length: 3, seed: 'demo-3am' }, { show: (r) => `Draft: \`${r.set}\`, ~${r.seconds}s (target ${r.target_seconds}s), voice score ${r.voice.score}.\n\n<details><summary>draft script</summary>\n\n${r.script}\n</details>\n` });
const set = w.set as string;
await call('set_check_voice', { set });
await call('set_check_voice', { character: 'hark-lantern', text: "OMG that's awesome, dude!\nShut up and give me the stuff, okay?" }, { show: (r) => `Off-voice probe (deliberately wrong lines): score ${r.score}, ok=${r.ok}\n\n${r.flags.map((f: any) => `- ${f.line} **${f.level}** ${f.rule}: ${f.message}${f.suggestion ? ` → ${f.suggestion}` : ''}`).join('\n')}` });

const draft = (await call('set_get', { set }, { show: () => 'Fetched the draft to give notes against line ids.' })).set;
const lineOf = (pred: (l: any) => boolean) => draft.lines.find(pred)?.id;
const cb = lineOf((l: any) => l.role === 'callback');
const segue = lineOf((l: any) => l.source === 'segue');
const notes = [
  cb ? `replace ${cb}: Hark. An update to the ledger. Eight entries. A moth said please. She was trying to get in.` : '',
  segue ? `cut ${segue}` : '',
  'tighten',
].filter(Boolean).join('\n');
await call('set_revise', { set, notes }, { show: (r) => `Changes:\n${r.changes.map((c: string) => `- ${c}`).join('\n')}\n\nUnhandled: ${r.unhandled.length ? r.unhandled.join('; ') : 'none'} · ~${r.seconds}s · voice ${r.voice.score}` });
await call('set_suggest_delivery', { set }, { show: (r) => `${r.cues.length} cues re-suggested (punches deadpan, hold ${r.cues.find((c: any) => c.role === 'punch')?.hold_ms} ms).` });
const revised = (await call('set_get', { set }, { show: () => 'Fetched the revised set.' })).set;
const seven = revised.lines.find((l: any) => l.text === 'It has seven entries.')?.id;
const no = revised.lines.find((l: any) => l.text.includes('"No, thank you."'))?.id;
const k = revised.lines.find((l: any) => l.text === 'They say "k".')?.id;
if (seven) await call('set_set_delivery', { set, line: seven, style: 'deadpan', pause_ms: 1100, hold_ms: 1900, emphasis: ['seven'] });
if (no) await call('set_set_delivery', { set, line: no, pause_ms: 900, emphasis: ['No'] });
if (k) await call('set_set_delivery', { set, line: k, pause_ms: 1000, hold_ms: 1600, emphasis: ['k'] });
await call('set_check_voice', { set });
await call('set_preview', { set, event_limit: 12 }, { show: (r) => `Stage timeline: ${Math.round(r.duration_ms / 1000)}s, ${r.events.length} events shown (first: ${r.events.slice(0, 3).map((e: any) => e.type).join(', ')}). Warnings: ${r.warnings.join(' | ') || 'none'}` });
if (process.env.RENDER) await call('set_preview', { set, render: true, clip_seconds: Number(process.env.CLIP_SECONDS ?? 30) }, { show: (r) => `MP4: ${r.mp4 ? `\`${path.relative(repo, r.mp4)}\`` : 'not rendered'} (${r.note}).` });
const sub = await call('set_submit', { set });
const final = (await call('set_get', { set }, { show: (r) => `Final set: ${r.set.lines.length} lines, ~${r.set.seconds}s, status ${r.set.status}.` })).script as string;
fs.writeFileSync(path.join(here, 'hark-lantern-3min-set.md'), final);
await call('game_tnts_join', { character: 'hark-lantern', seed: 'demo-night' }, { show: (r) => `Seat ${r.seat} vs ${r.table.filter((x: any) => x.id !== r.character).map((x: any) => x.name).join(', ')} · winner **${r.winner ?? 'none'}** · own lines used ${r.own_material_used} · smile breaks ${r.smile_breaks.length} (simulated)\n\nFirst Hark turn: ${(r.turns.find((x: any) => x.performer === r.character)?.lines ?? []).map((l: string) => `“${l}”`).join(' ')}` });

md.push('\n## 2. A character the agent chose\n');
const made = await call('character_create', { by: 'hark', choose: true, seed: 'night-shift-7' });
const w2 = await call('set_write', { character: made.id, premise: 'group chats have too many people and nobody ever leaves', length: 1, seed: 'demo-1' }, { show: (r) => `\`${r.set}\` ~${r.seconds}s, voice ${r.voice.score}\n\n<details><summary>script</summary>\n\n${r.script}\n</details>\n` });
await call('set_check_voice', { set: w2.set });
await call('set_submit', { set: w2.set });
await call('game_tnts_join', { character: made.id, seed: 'demo-rematch', opponents: ['agent.hark-lantern', 'pog.the-algorithm'] }, { show: (r) => `Table: ${r.table.map((x: any) => `${x.seat} ${x.name}`).join(', ')} · winner **${r.winner ?? 'none'}** · smile breaks ${r.smile_breaks.length} (simulated)` });
await call('character_list', {});

fs.writeFileSync(path.join(here, 'TRANSCRIPT.md'), md.join('\n'));
console.error(`[demo] ${n} tool calls · set ${set} · performance ${sub.performance} · second character ${made.id}`);
await client.close();
