/**
 * Brand rename guard: the old product name must not come back outside the
 * allow-listed infrastructure names (deploy hostnames, Cloudflare worker /
 * bucket / database names, the GitHub repo slug, server paths, persisted
 * identifiers and wire-contract ids). See docs/BRAND-RENAME.md for why each
 * one stays.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
// built from parts so this file does not match itself
const OLD = ['freak', '[ _-]?', 'town'].join('');
const HIT = new RegExp(OLD, 'i');

/** Spans that may keep the old name (infra + persisted ids). Mirrors docs/BRAND-RENAME.md. */
export const ALLOW: RegExp[] = [
  /https?:\/\/[^\s'"`)>\]]*/g,                                          // any URL: deploy hostnames, the GitHub repo, workers.dev
  new RegExp(`(?:prx0r|/root|/home/ubuntu|\\.venvs|~|/srv|/opt|/workspace/work)/${OLD}(?![-\\w])`, 'gi'), // server paths, venvs, repo slug
  new RegExp(`${OLD}-(?:trial|perform)\\b`, 'gi'),                      // cloudflared tunnel, perform worker
  new RegExp(`${OLD}-(?:postgres|dev-secret-change-in-prod|guest|creator|theme|assets)\\b`, 'gi'), // hyperdrive, dev secret, hash salts, storage key, bucket option
  new RegExp(`r2://${OLD}|${OLD}/|\`${OLD}\`|["']${OLD}["']|^${OLD}$`, 'gim'), // R2 bucket / D1 / worker name values
  /postgresql[^\s"']*/g,                                                // Postgres DSNs (db + role name)
  new RegExp(`${OLD}_ai|${OLD}_DRAW_V1|${OLD}\\.service|${OLD}_(?:id|draft|admin_key|session_id)\\b|${OLD}_SOURCE`, 'gi'), // persisted enum, draw algorithm id, systemd unit, storage keys, migration pin
  new RegExp(`"service": "${OLD}"`, 'gi'),                              // health-check service id
  new RegExp(`\\(\\?:${OLD}\\|FUNNIER\\)`, 'gi'),                        // skin title matcher still accepts the legacy brand from a box on older code
  new RegExp(`${OLD}\\.(?!newsroom\\.|live\\.sets)[a-z_]+(?:\\.[a-z_]+)*[./]v\\d+`, 'gi'), // wire contract ids (sealed bundles, golden fixtures)
];

/** Paths whose content may mention the old name freely. */
const SKIP = [/^packages\/contracts\/tests\/brand-rename\.test\.ts$/, /^docs\/BRAND-RENAME\.md$/, /\.(png|jpe?g|gif|webp|glb|vrm|wav|mp3|mp4|ico|pdf|woff2?|ttf|zip|gz)$/i];
/** Paths (file names) allowed to keep the old name. */
const PATH_ALLOW = [/^deploy\/[^/]*\.service$/];

function files(): string[] {
  try {
    return execFileSync('git', ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], { cwd: REPO, encoding: 'utf8', maxBuffer: 64 << 20 }).split('\0').filter(Boolean);
  } catch {
    return [];
  }
}

describe('brand rename leftovers', () => {
  const list = files();
  it('runs inside the git checkout', () => { expect(list.length).toBeGreaterThan(100); });

  it('no old-brand file or directory names outside the allow-list', () => {
    const bad = list.filter((f) => HIT.test(f) && !PATH_ALLOW.some((p) => p.test(f)) && !SKIP.some((p) => p.test(f)));
    expect(bad).toEqual([]);
  });

  it('no old-brand text outside the allow-listed infra names', () => {
    const leftovers: string[] = [];
    for (const f of list) {
      if (SKIP.some((p) => p.test(f))) continue;
      const abs = path.join(REPO, f);
      let text: string;
      try {
        const buf = fs.readFileSync(abs);
        if (buf.subarray(0, 8000).includes(0)) continue;
        text = buf.toString('utf8');
      } catch { continue; }
      if (!HIT.test(text)) continue;
      text.split('\n').forEach((line, i) => {
        if (!HIT.test(line)) return;
        let rest = line;
        for (const re of ALLOW) rest = rest.replace(re, '');
        if (HIT.test(rest)) leftovers.push(`${f}:${i + 1}: ${line.trim().slice(0, 140)}`);
      });
    }
    expect(leftovers).toEqual([]);
  });
});
