/**
 * An agent creates (and persists) its own character.
 *
 *   npx vite-node packages/party/cli/create-identity.ts -- --by hark --name "Hark Lantern" --head lantern \
 *       --writes observational,deadpan --delivery deadpan --bio "..." --catchphrase "..." [--voice en-GB-RyanNeural] [--eyes 1-3] [--seed x]
 *   (npm run party:identity -- --by <agent> ...)   omitted fields are chosen by the agent's seeded RNG
 *
 * Writes:
 *   packages/party/identities/<id>.json         the identity record (name, voice, look, persona, taste)
 *   packages/party/identities/registry.json     regenerated from every identities/*.json (what getPartyIdentity reads)
 *   apps/live/public/identities/<id>.glb        procedural body with ARKit morphs (jawOpen, smile, blink)
 */
import path from 'node:path';
import { createIdentity, type IdentityBrief } from '../src/identity';
import { persistIdentity } from './persist-identity';
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
  eyes: arg('eyes') ? Number(arg('eyes')) : undefined,
};
const idn = createIdentity(brief);
console.log(JSON.stringify(persistIdentity(repo, idn), null, 1));
