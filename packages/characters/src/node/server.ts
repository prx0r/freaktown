/**
 * The CHARACTERS MCP server. Tools are registered with underscore names
 * (character_create, set_write, ...) because Claude and OpenAI tool-name rules
 * reject dots; set CHARACTERS_MCP_DOTTED=1 to also register the dotted
 * spellings (character.create, set.write, ...) for clients that allow them.
 *
 * Transports: stdio (default) and streamable HTTP (stateless, POST /mcp).
 */
import http from 'node:http';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import { z } from 'zod';
import { DELIVERIES, MECHANISMS } from '@funnier/party';
import { CharacterStudio } from './studio';

const delivery = z.enum(['pause', ...DELIVERIES] as unknown as [string, ...string[]]);
const mechanism = z.enum(MECHANISMS as unknown as [string, ...string[]]);

export interface ToolDef { name: string; title: string; description: string; shape: z.ZodRawShape; run: (s: CharacterStudio, a: any) => unknown; readOnly?: boolean }

export const TOOLS: ToolDef[] = [
  { name: 'character_create', title: 'Create a character', description: 'Create a persistent comedy character from a premise, or let the agent choose (choose:true). Writes the party identity, a full theory (want/need, flaw, status, game, voice, taste, worldview, arc...), the procedural GLB with ARKit morphs, and registers it so every room (TNTS, /minute, /characters3) can seat it. adopt:<identity id> builds a theory for an existing identity instead.',
    shape: { by: z.string().describe('who is creating, e.g. "hark" or "claude"'), premise: z.string().optional().describe('e.g. "a ghost who works as an estate agent"'), choose: z.boolean().optional().describe('let the agent choose everything'), seed: z.string().optional(), name: z.string().optional(), bio: z.string().optional(), catchphrase: z.string().optional(), delivery: z.enum(DELIVERIES as unknown as [string, ...string[]]).optional(), writes: z.array(mechanism).optional(), head: z.enum(['sphere', 'box', 'lantern', 'blob']).optional(), voice_id: z.string().optional(), adopt: z.string().optional().describe('existing identity id to adopt, e.g. agent.hark-lantern') },
    run: (s, a) => s.create(a) },
  { name: 'character_get', title: 'Get a character', description: 'The identity, full theory (optionally as the rendered THEORY.md), sets and performances of one character. Accepts id, slug or name.', readOnly: true,
    shape: { character: z.string(), include_markdown: z.boolean().optional() }, run: (s, a) => s.get(a) },
  { name: 'character_list', title: 'List characters', description: 'Every character in the studio with logline, delivery, set count and appearances.', readOnly: true, shape: {}, run: (s) => s.list() },
  { name: 'character_update_theory', title: 'Update a character theory', description: 'Deep-merge a patch into the theory (objects merge, arrays replace; material/callbacks/relationships upsert by id/who; null deletes). Validated, changelogged, THEORY.md regenerated.',
    shape: { character: z.string(), patch: z.record(z.any()).describe('partial funnier.character-theory/v1'), note: z.string().optional(), by: z.string().optional(), replace: z.array(z.enum(['material', 'callbacks', 'relationships'])).optional().describe('replace these lists wholesale instead of upserting') }, run: (s, a) => s.updateTheory(a) },
  { name: 'set_write', title: 'Write a set', description: 'Write a 1, 3 or 5 minute set in the character\'s voice from a premise: opener, bits as setup/punch/tag(/act-out) ordered as a game (establish → heighten → explore → top), a callback and a closer. Deterministic template writer (LLM hook off). Returns the script and a voice check.',
    shape: { character: z.string(), premise: z.string(), length: z.union([z.literal(1), z.literal(3), z.literal(5)]), seed: z.string().optional(), title: z.string().optional() }, run: (s, a) => s.write(a) },
  { name: 'set_get', title: 'Get a set', description: 'A set as JSON plus its readable script.', readOnly: true, shape: { set: z.string() }, run: (s, a) => s.getSet(a) },
  { name: 'set_revise', title: 'Revise a set', description: 'Apply notes, one per line or ";"-separated: "cut l7", "cut beat 3", "replace l7: <text>", "tag l7: <text>", "swap beats 2 4", "tighten", "slower", "faster", "more deadpan", "punch up beat 3", "add callback". Unknown notes are reported as unhandled, never guessed.',
    shape: { set: z.string(), notes: z.string() }, run: (s, a) => s.revise(a) },
  { name: 'set_suggest_delivery', title: 'Suggest delivery', description: 'Re-suggest delivery style, pause, hold and emphasis for every line (or the given lines) from the role and the character\'s physicality.',
    shape: { set: z.string(), lines: z.array(z.string()).optional() }, run: (s, a) => s.suggestDelivery(a) },
  { name: 'set_set_delivery', title: 'Set delivery for a line', description: 'Override one line: style (deadpan|deliberate|manic|warm|conspiratorial|pause), pause before (ms), hold after (ms), emphasis words.',
    shape: { set: z.string(), line: z.string(), style: delivery.optional(), pause_ms: z.number().int().min(0).max(10000).optional(), hold_ms: z.number().int().min(0).max(10000).optional(), emphasis: z.array(z.string()).optional() }, run: (s, a) => s.setDelivery(a) },
  { name: 'set_check_voice', title: 'Check voice', description: 'Consistency checker: flags off-voice lines (register, contractions, sentence length, exclamations, delivery fit), forbidden words, taboo lines and safety rails. Pass a set, or a character + text.', readOnly: true,
    shape: { set: z.string().optional(), character: z.string().optional(), text: z.string().optional() }, run: (s, a) => s.checkVoice(a) },
  { name: 'set_preview', title: 'Preview a set', description: 'Stage events for the comedy-club stage (the same timeline /sketch plays). render:true also renders a short MP4 (needs a built apps/live and Chromium; can take minutes).',
    shape: { set: z.string(), render: z.boolean().optional(), clip_seconds: z.number().min(3).max(300).optional(), event_limit: z.number().int().min(1).max(2000).optional() }, run: (s, a) => s.preview(a) },
  { name: 'set_submit', title: 'Submit a set', description: 'Submit as a funnier.sketch/v1 performance (blocked by voice-check errors unless force:true). Saved with the character and to apps/live/public/sketches so /sketch/<id> plays it.',
    shape: { set: z.string(), force: z.boolean().optional() }, run: (s, a) => s.submit(a) },
  { name: 'game_tnts_join', title: 'Join Try-Not-To-Smile', description: 'Seat the character at a Try-Not-To-Smile table as an agent player against resident agents. Its turns use its own sets first; smiles are the party taste model (simulated, seeded). Returns the table, turns, smile breaks and standings.',
    shape: { character: z.string(), seed: z.string().optional(), opponents: z.array(z.string()).optional() }, run: (s, a) => s.tntsJoin(a) },
];

export function buildServer(studio = new CharacterStudio(), opts: { dotted?: boolean } = {}): McpServer {
  const server = new McpServer({ name: 'funnier-characters', version: '0.1.0' }, { instructions: 'The /characters3 studio. Typical flow: character_create (or character_list/get) → character_update_theory → set_write → set_check_voice → set_revise → set_suggest_delivery / set_set_delivery → set_preview → set_submit → game_tnts_join. All material must be original.' });
  const dotted = opts.dotted ?? process.env.CHARACTERS_MCP_DOTTED === '1';
  for (const t of TOOLS) {
    const names = dotted ? [t.name, t.name.replace('_', '.')] : [t.name];
    for (const name of names) {
      server.registerTool(name, { title: t.title, description: t.description, inputSchema: t.shape, annotations: { readOnlyHint: !!t.readOnly, openWorldHint: false } }, async (args: Record<string, unknown>) => {
        try {
          const out = t.run(studio, args ?? {});
          return { content: [{ type: 'text' as const, text: JSON.stringify(out, null, 1) }] };
        } catch (e) {
          return { isError: true, content: [{ type: 'text' as const, text: (e as Error).message }] };
        }
      });
    }
  }
  return server;
}

export async function serveStdio(studio?: CharacterStudio): Promise<void> {
  const server = buildServer(studio);
  await server.connect(new StdioServerTransport());
}

/** Streamable HTTP, stateless: a fresh server + transport per POST /mcp (the SDK's stateless pattern). */
export function serveHttp(port = 8765, host = '127.0.0.1', studio = new CharacterStudio()): http.Server {
  const srv = http.createServer(async (req, res) => {
    const url = (req.url ?? '').split('?')[0];
    if (url === '/health') { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify({ ok: true, tools: TOOLS.length })); return; }
    if (url !== '/mcp') { res.writeHead(404).end(); return; }
    if (req.method !== 'POST') { res.writeHead(405, { allow: 'POST' }).end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32000, message: 'Method not allowed (stateless server: POST only)' }, id: null })); return; }
    const chunks: Buffer[] = [];
    for await (const c of req) chunks.push(c as Buffer);
    let body: unknown;
    try { body = JSON.parse(Buffer.concat(chunks).toString('utf8') || 'null'); } catch { res.writeHead(400).end(); return; }
    const server = buildServer(studio);
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
    res.on('close', () => { transport.close(); server.close(); });
    await server.connect(transport);
    await transport.handleRequest(req, res, body);
  });
  srv.listen(port, host);
  return srv;
}
