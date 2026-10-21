import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/**
 * Serve/copy repo avatars (static/avatars/*.vrm|glb) under /avatars/ without
 * duplicating the bytes into apps/live/public. Character-mesh GLBs pulled
 * by scripts/fetch_r2_media.py (data/character-meshes, gitignored) are
 * exposed under /meshes/ when present locally.
 */
function repoAssets(): Plugin {
  const roots: Record<string, string> = {
    '/avatars/': path.resolve(__dirname, '../../static/avatars'),
    '/meshes/': path.resolve(__dirname, '../../data/character-meshes'),
  };
  return {
    name: 'freaktown-repo-assets',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = (req.url ?? '').split('?')[0];
        const base = server.config.base.replace(/\/$/, '');
        for (const [prefix, dir] of Object.entries(roots)) {
          const p = base + prefix;
          if (url.startsWith(p)) {
            const file = path.join(dir, decodeURIComponent(url.slice(p.length)));
            if (file.startsWith(dir) && fs.existsSync(file) && fs.statSync(file).isFile()) {
              res.setHeader('Content-Type', 'model/gltf-binary');
              fs.createReadStream(file).pipe(res);
              return;
            }
          }
        }
        next();
      });
    },
    generateBundle() {
      const dir = roots['/avatars/'];
      if (!fs.existsSync(dir)) return;
      for (const f of fs.readdirSync(dir)) {
        if (/\.(vrm|glb)$/i.test(f)) {
          this.emitFile({ type: 'asset', fileName: `avatars/${f}`, source: fs.readFileSync(path.join(dir, f)) });
        }
      }
    },
  };
}

// LIVE_BASE: where the app is mounted, e.g. "/perform/live/" behind Caddy.
export default defineConfig({
  base: process.env.LIVE_BASE ?? '/',
  // poker-ts (MIT) requires node's `assert`; give the browser a 4-line shim.
  resolve: { alias: { assert: path.resolve(__dirname, 'src/shims/assert.ts'), crypto: path.resolve(__dirname, 'src/shims/crypto.ts') } },
  plugins: [react(), repoAssets()],
  server: {
    port: 5173,
    // `npm run dev` + `wrangler dev` (8787): proxy the EpisodeRoom routes.
    proxy: process.env.LIVE_ROOM_PROXY
      ? { '/live/': { target: process.env.LIVE_ROOM_PROXY, ws: true, changeOrigin: true,
          bypass: (req) => (req.headers.accept?.includes('text/html') ? req.url : undefined) } }
      : undefined,
  },
  build: { outDir: 'dist', chunkSizeWarningLimit: 1600, sourcemap: false },
});
