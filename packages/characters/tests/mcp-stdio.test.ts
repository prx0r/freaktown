/**
 * MCP client smoke test over stdio: spawn the real server binary (vite-node
 * bin/characters-mcp.ts) with a temp library, list tools, run a short flow,
 * and check the error path. Also exercises the streamable HTTP transport.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { CharacterStore, CharacterStudio, serveHttp, TOOLS } from '../src/node';

const repo = path.resolve(__dirname, '../../..');
const EXPECTED = ['character_create', 'character_get', 'character_list', 'character_update_theory', 'set_write', 'set_get', 'set_revise', 'set_suggest_delivery', 'set_set_delivery', 'set_check_voice', 'set_preview', 'set_submit', 'game_tnts_join'];

function tempEnv() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'characters-mcp-'));
  fs.mkdirSync(path.join(root, 'ids'));
  return { root, env: { CHARACTERS_LIBRARY: path.join(root, 'lib'), PARTY_IDENTITIES_DIR: path.join(root, 'ids'), CHARACTERS_GLB_DIR: path.join(root, 'glb'), CHARACTERS_SKETCH_DIR: path.join(root, 'sk'), CHARACTERS_PREVIEW_DIR: path.join(root, 'pv') } };
}
const parse = (r: unknown) => JSON.parse((r as { content: Array<{ text: string }> }).content[0].text);

describe('MCP stdio smoke', () => {
  it('lists the tools and runs create → write → check → submit → tnts over stdio', async () => {
    const { env } = tempEnv();
    const transport = new StdioClientTransport({ command: path.join(repo, 'node_modules/.bin/vite-node'), args: [path.join(repo, 'packages/characters/bin/characters-mcp.ts')], cwd: repo, env: { ...process.env, ...env, CHARACTERS_MCP_DOTTED: '1' } as Record<string, string>, stderr: 'pipe' });
    const client = new Client({ name: 'smoke', version: '0' });
    await client.connect(transport);
    try {
      const names = (await client.listTools()).tools.map((t) => t.name);
      for (const n of EXPECTED) { expect(names).toContain(n); expect(names).toContain(n.replace('_', '.')); }
      const made = parse(await client.callTool({ name: 'character_create', arguments: { by: 'smoke', choose: true, seed: 'smoke' } }));
      expect(made.id).toMatch(/^agent\./);
      const w = parse(await client.callTool({ name: 'set.write', arguments: { character: made.id, premise: 'printers have moods and no off switch', length: 1 } }));
      expect(w.script).toContain('PUNCH');
      const v = parse(await client.callTool({ name: 'set_check_voice', arguments: { set: w.set } }));
      expect(typeof v.score).toBe('number');
      const sub = parse(await client.callTool({ name: 'set_submit', arguments: { set: w.set } }));
      expect(sub.schema).toBe('funnier.sketch/v1');
      expect(fs.existsSync(path.join(env.CHARACTERS_SKETCH_DIR, `${sub.performance}.sketch.json`))).toBe(true);
      const tn = parse(await client.callTool({ name: 'game_tnts_join', arguments: { character: made.id, seed: 'smoke' } }));
      expect(tn.simulated).toBe(true);
      const bad = await client.callTool({ name: 'character_get', arguments: { character: 'nobody-at-all' } });
      expect(bad.isError).toBe(true);
    } finally { await client.close(); }
  }, 120_000);
});

describe('MCP streamable HTTP', () => {
  it('serves the same tools statelessly on POST /mcp', async () => {
    const { env } = tempEnv();
    const store = new CharacterStore({ library: env.CHARACTERS_LIBRARY, identities: env.PARTY_IDENTITIES_DIR, glb: env.CHARACTERS_GLB_DIR, sketches: env.CHARACTERS_SKETCH_DIR, previews: env.CHARACTERS_PREVIEW_DIR });
    const port = 18765 + Math.floor(Math.random() * 1000);
    const srv = serveHttp(port, '127.0.0.1', new CharacterStudio(store));
    const client = new Client({ name: 'http-smoke', version: '0' });
    try {
      await client.connect(new StreamableHTTPClientTransport(new URL(`http://127.0.0.1:${port}/mcp`)));
      expect((await client.listTools()).tools).toHaveLength(TOOLS.length);
      const made = parse(await client.callTool({ name: 'character_create', arguments: { by: 'http', premise: 'a nervous cuckoo clock who lives in a co-working space' } }));
      const list = parse(await client.callTool({ name: 'character_list', arguments: {} }));
      expect(list.characters.map((c: { id: string }) => c.id)).toContain(made.id);
    } finally { await client.close(); srv.close(); }
  }, 60_000);
});
