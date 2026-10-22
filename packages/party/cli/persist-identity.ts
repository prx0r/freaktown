/** Persist an identity the way the identity flow does: identities/<id>.json, regenerated registry.json, public GLB. */
import fs from 'node:fs';
import path from 'node:path';
import { validateIdentity, type PartyIdentity } from '../src/identity';
import { identityGlb, readGlbJson } from '../src/glb';

export function persistIdentity(repo: string, idn: PartyIdentity) {
  const dir = path.join(repo, 'packages/party/identities');
  fs.writeFileSync(path.join(dir, `${idn.id}.json`), JSON.stringify(idn, null, 2) + '\n');
  const all: PartyIdentity[] = fs.readdirSync(dir).filter((f) => f.endsWith('.json') && f !== 'registry.json').sort().map((f) => JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8')));
  for (const x of all) { const p = validateIdentity(x); if (p.length) throw new Error(`${x.id}: ${p.join('; ')}`); }
  fs.writeFileSync(path.join(dir, 'registry.json'), JSON.stringify({ identities: all }, null, 2) + '\n');
  const glb = identityGlb(idn);
  const gdir = path.join(repo, 'apps/live/public/identities');
  fs.mkdirSync(gdir, { recursive: true });
  fs.writeFileSync(path.join(gdir, `${idn.id}.glb`), glb);
  const g = readGlbJson(glb);
  return { id: idn.id, name: idn.name, glb: `apps/live/public/identities/${idn.id}.glb`, bytes: glb.length, meshes: g.json.meshes.map((m: { name: string }) => m.name), morphs: g.json.meshes.flatMap((m: { extras?: { targetNames?: string[] } }) => m.extras?.targetNames ?? []), registry: all.length };
}
