import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SketchScriptV1 } from '../src';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '../../..');
export const DEMO_IDS = ['wall-of-news', 'the-tell'] as const;
export function demo(id: string): SketchScriptV1 {
  return JSON.parse(fs.readFileSync(path.join(REPO, 'apps/live/public/sketches', `${id}.sketch.json`), 'utf8'));
}

/** A small two-hander exercising every direction kind. */
export function mini(): SketchScriptV1 {
  return {
    schema: 'funnier.sketch/v1', id: 'mini', title: 'Mini', set: 'podcast',
    cast: [
      { role: 'host', identity: 'pog.doug-deadline', seat: 'seat1' },
      { role: 'guest', identity: 'pog.pete-pebble', seat: 'seat2' },
      { role: 'walker', identity: 'guest.wren', name: 'Wren', seat: 'seat3' },
    ],
    scenes: [{ id: 's', beats: [
      { id: 'b1', kind: 'setup', items: [
        { type: 'line', who: 'host', text: 'Welcome back to the show, where nothing ever happens and we like it that way.' },
        { type: 'line', who: 'guest', text: 'Thanks for having me. I brought a rock.' },
        { type: 'look', who: 'host', at: 'guest', double_take: true },
      ] },
      { id: 'b2', kind: 'game', items: [
        { type: 'line', who: 'host', text: 'Why did you bring a rock to a podcast?' },
        { type: 'line', who: 'guest', text: 'It is my co-host. It does not talk, but it listens, which is more than I can say for you.' },
        { type: 'react', who: 'host', kind: 'eye-roll', during: 'prev', from_end_ms: 400 },
        { type: 'hold_for_laugh', ms: 1500 },
      ] },
      { id: 'b3', kind: 'turn', items: [
        { type: 'move', who: 'walker', to: 'door', ms: 1200, wait: true },
        { type: 'line', who: 'walker', text: 'I am here to collect the rock. It owes us rent.' },
        { type: 'gesture', who: 'guest', kind: 'shrug' },
        { type: 'pause', ms: 800 },
        { type: 'line', who: 'guest', text: 'He has been living in my pocket for free.' },
        { type: 'react', who: 'host', kind: 'laugh-break' },
        { type: 'hold_for_laugh' },
      ] },
      { id: 'b4', kind: 'button', items: [
        { type: 'button' },
        { type: 'line', who: 'host', to: 'camera', text: 'We will be right back.' },
        { type: 'blackout', fade_ms: 700 },
      ] },
    ] }],
  };
}
