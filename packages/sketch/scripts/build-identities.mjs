#!/usr/bin/env node
/**
 * Snapshot the persistent character identities (assets/character-meshes/cast/)
 * into packages/sketch/src/identities.generated.json, so the sketch layer
 * (browser + node) resolves `pog.*` identity ids without a parallel registry.
 *
 * Sources (canonical, unchanged): cast-index.json (id, name, mesh, engine),
 * lifecycle.json (voice), motion-<slug>.json (pog.motion-style.v1:
 * temperament, reaction_delay_ms, gesture_frequency, signature_action).
 *
 *   node packages/sketch/scripts/build-identities.mjs [--check]
 * --check exits 1 when the snapshot is stale (CI / the drift unit test).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../../..');
const castDir = path.join(repo, 'assets/character-meshes/cast');
const out = path.join(repo, 'packages/sketch/src/identities.generated.json');

export function buildIdentities() {
  const index = JSON.parse(fs.readFileSync(path.join(castDir, 'cast-index.json'), 'utf8'));
  const life = JSON.parse(fs.readFileSync(path.join(castDir, 'lifecycle.json'), 'utf8'));
  const voice = new Map((life.characters ?? []).map((c) => [c.id, c.voice]));
  const ids = index.cast.map((c) => {
    const slug = c.id.replace(/^pog\./, '');
    const mf = path.join(castDir, `motion-${slug}.json`);
    const m = fs.existsSync(mf) ? JSON.parse(fs.readFileSync(mf, 'utf8')) : null;
    return {
      id: c.id,
      name: c.name,
      family: c.file.split('-')[0],
      mesh: c.mesh,
      engine: c.engine,
      voice: voice.get(c.id) ?? null,
      motion: m ? {
        family: m.family ?? null,
        energy: m.temperament?.energy ?? null,
        confidence: m.temperament?.confidence ?? null,
        nervousness: m.temperament?.nervousness ?? null,
        theatricality: m.temperament?.theatricality ?? null,
        reaction_delay_ms: m.signature?.reaction_delay_ms ?? null,
        gesture_frequency: m.signature?.gesture_frequency ?? null,
        signature_action: m.signature?.signature_action ?? null,
      } : null,
    };
  });
  return { source: 'assets/character-meshes/cast (cast-index.json + lifecycle.json + motion-*.json)', count: ids.length, identities: ids };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const next = JSON.stringify(buildIdentities(), null, 1) + '\n';
  if (process.argv.includes('--check')) {
    const cur = fs.existsSync(out) ? fs.readFileSync(out, 'utf8') : '';
    if (cur !== next) { console.error('identities.generated.json is stale: run node packages/sketch/scripts/build-identities.mjs'); process.exit(1); }
    console.log('identities snapshot up to date');
  } else {
    fs.writeFileSync(out, next);
    console.log('wrote', path.relative(repo, out));
  }
}
