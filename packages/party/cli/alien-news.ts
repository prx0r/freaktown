/**
 * Alien News (P5): create the two alien anchors through the identity flow and
 * write the newsroom rundown the render CLI turns into an MP4.
 *
 *   npx vite-node packages/party/cli/alien-news.ts [-- --no-subs] [--seed ep1]
 *   node packages/newsroom/cli/render.mjs apps/live/public/newsroom/alien-news.json -o alien-news.mp4 --build
 *
 * Writes:
 *   packages/party/identities/agent.zorvex-quillam.json, agent.mib-trellune.json (+ registry.json)
 *   apps/live/public/identities/<id>.glb              procedural bodies (dome head + 3 eyes, blob + 1 eye)
 *   apps/live/public/newsroom/alien-news.json        funnier.newsroom.rundown/v1
 *   apps/live/public/newsroom/alien-news.lines.json  each gibberish line, its subtitle and the visemes it drives
 */
import fs from 'node:fs';
import path from 'node:path';
import { alienNewsRundown } from '../src/alien';
import { persistIdentity } from './persist-identity';

const repo = path.resolve(__dirname, '../../..');
const argv = process.argv.slice(2);
const seedAt = argv.indexOf('--seed');
const { rundown, anchors, lines } = alienNewsRundown({ seed: seedAt >= 0 ? argv[seedAt + 1] : undefined, subtitles: !argv.includes('--no-subs') });
const made = anchors.map((a) => persistIdentity(repo, a));
const out = path.join(repo, 'apps/live/public/newsroom');
fs.writeFileSync(path.join(out, 'alien-news.json'), JSON.stringify(rundown, null, 1) + '\n');
fs.writeFileSync(path.join(out, 'alien-news.lines.json'), JSON.stringify({ rundown: rundown.id, lines }, null, 1) + '\n');
console.log(JSON.stringify({ anchors: made, rundown: 'apps/live/public/newsroom/alien-news.json', lines: lines.length }, null, 1));
