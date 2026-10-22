/**
 * characters-mcp: the /characters3 studio as an MCP server.
 *
 *   npx vite-node packages/characters/bin/characters-mcp.ts                 # stdio
 *   npx vite-node packages/characters/bin/characters-mcp.ts -- --http [--port 8765] [--host 127.0.0.1]
 *
 * Env: CHARACTERS_LIBRARY, PARTY_IDENTITIES_DIR, CHARACTERS_GLB_DIR, CHARACTERS_SKETCH_DIR,
 *      CHARACTERS_PREVIEW_DIR (paths), CHARACTERS_MCP_DOTTED=1 (also register dotted tool names).
 * stdout belongs to the protocol in stdio mode: logs go to stderr.
 */
import { serveHttp, serveStdio } from '../src/node/server';

const argv = process.argv.slice(2);
const arg = (k: string) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : undefined; };

if (argv.includes('--http')) {
  const port = Number(arg('port') ?? process.env.PORT ?? 8765);
  const host = arg('host') ?? '127.0.0.1';
  serveHttp(port, host);
  console.error(`[characters-mcp] streamable HTTP on http://${host}:${port}/mcp`);
} else {
  serveStdio().catch((e) => { console.error('[characters-mcp]', e); process.exit(1); });
}
