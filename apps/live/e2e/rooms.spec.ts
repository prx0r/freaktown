import { test, expect } from '@playwright/test';
import { spawn, type ChildProcess } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/** Always-on rooms: lobby lists the four rooms with residents; a human takes a seat and leaves. */
const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');
const PORT = 8792;
let srv: ChildProcess | null = null;

test.beforeAll(async () => {
  srv = spawn('npx', ['vite-node', 'packages/party/server/rooms-server.ts'], { cwd: repo, env: { ...process.env, ROOMS_PORT: String(PORT) }, stdio: 'pipe', detached: true });
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/rooms`); if (r.ok) return; } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error('rooms server did not start');
});
test.afterAll(() => { if (srv?.pid) { try { process.kill(-srv.pid); } catch { srv.kill(); } } });

test('lobby lists always-on rooms with residents (server)', async ({ page }) => {
  await page.goto(`/rooms?server=http://127.0.0.1:${PORT}`);
  await expect(page.getByTestId('rooms-mode')).toContainText('connected to rooms server');
  for (const id of ['podcast', 'poker', 'tnts', 'newsroom']) await expect(page.getByTestId(`room-card-${id}`)).toBeVisible();
  await expect(page.getByTestId('room-card-podcast')).toContainText('Pete the Pebble');
});

test('take a seat in the podcast and leave again', async ({ page }) => {
  await page.goto(`/rooms/podcast?server=http://127.0.0.1:${PORT}&quality=low`);
  await expect(page.getByTestId('room-mode')).toContainText('rooms server');
  await expect(page.getByTestId('room-caption')).toBeVisible({ timeout: 30_000 });
  await page.getByTestId('room-name').fill('Ana');
  await page.getByTestId('room-join').click();
  await expect(page.getByTestId('room-me')).toContainText(/you are in seat\d/);
  const seat = (await page.getByTestId('room-me').innerText()).match(/seat\d/)![0];
  await expect(page.getByTestId(`room-seat-${seat}`)).toContainText('Ana', { timeout: 10_000 });
  await page.getByTestId('room-leave').click();
  await expect(page.getByTestId('room-join')).toBeVisible();
});

test('rooms run in the tab when no server answers', async ({ page }) => {
  await page.goto('/rooms?local=1');
  await expect(page.getByTestId('rooms-mode')).toContainText('running in this tab');
  await expect(page.getByTestId('room-card-newsroom')).toBeVisible();
});
