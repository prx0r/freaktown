/**
 * An agent creates (and persists) its own character.
 *
 *   npx vite-node packages/party/cli/create-identity.ts -- --by hark --name "Hark Lantern" --head lantern \
 *       --writes observational,deadpan --delivery deadpan --bio "..." --catchphrase "..." [--voice en-GB-RyanNeural] [--seed x]
 *   (npm run party:identity -- --by <agent> ...)   omitted fields are chosen by the agent's seeded RNG
 *
 * Writes:
 *   packages/party/identities/<id>.json         the identity record (name, voice, look, persona, taste)
 *   packages/party/identities/registry.json     regenerated from every identities/*.json (what getPartyIdentity reads)
 *   apps/live/public/identities/<id>.glb        procedural body with ARKit morphs (jawOpen, smile, blink)
 */
import fs from 'node:fs';
import path from 'node:path';
import { createIdentity, validateIdentity, type IdentityBrief, type PartyIdentity } from '../src/identity';
import { identityGlb, readGlbJson } from '../src/glb';
import type { Delivery, Mechanism } from '../src/jokes';

const repo = path.resolve(__dirname, '../../..');
const argv = process.argv.slice(2);
const arg = (k: string) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : undefined; };
const brief: IdentityBrief = {
  by: arg('by') ?? 'agent.anonymous',
  seed: arg('seed'),
  name: arg('name'),
  bio: arg('bio'),
  writes: arg('writes')?.split(',') as Mechanism[] | undefined,
  delivery: arg('delivery') as Delivery | undefined,
  catchphrase: arg('catchphrase'),
  head: arg('head') as IdentityBrief['head'],
  palette: arg('palette')?.split(','),
  voice: arg('voice') ? { engine: 'edge', id: arg('voice')! } : undefined,
};
const idn = createIdentity(brief);
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
console.log(JSON.stringify({ id: idn.id, name: idn.name, glb: `apps/live/public/identities/${idn.id}.glb`, bytes: glb.length, meshes: g.json.meshes.map((m: { name: string }) => m.name), morphs: g.json.meshes.flatMap((m: { extras?: { targetNames?: string[] } }) => m.extras?.targetNames ?? []), registry: all.length }, null, 1));
