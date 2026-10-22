/** CLI entry: npm run face:check -- <file.glb|.vrm> [--json]  (logic in ./faceCheck.ts) */
import { faceCheck, formatReport } from './faceCheck';

{
  const args = process.argv.slice(2).filter((a) => a !== '--');
  const files = args.filter((a) => !a.startsWith('--'));
  if (!files.length) { console.error('usage: npm run face:check -- <file.glb|.vrm> [more…] [--json]'); process.exit(2); }
  let code = 0;
  for (const f of files) {
    try {
      const r = faceCheck(f);
      console.log(args.includes('--json') ? JSON.stringify(r, (k, v) => (k === 'binding' ? { ...v } : v), 1) : formatReport(r));
      if (r.verdict !== 'ok') code = Math.max(code, 1);
    } catch (e) { console.error(`face:check ${f}: ${(e as Error).message}`); code = 2; }
  }
  process.exit(code);
}
