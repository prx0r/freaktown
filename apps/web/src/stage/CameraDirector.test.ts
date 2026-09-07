/**
 * CameraDirector unit tests — keys 1-6, callback timestamps,
 * invalid keys, and keyboard cleanup.
 */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { PerspectiveCamera } from 'three';
import { CameraDirector } from './CameraDirector';

function makeDirector() {
  const camera = new PerspectiveCamera(45, 1, 0.1, 100);
  return new CameraDirector(camera);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('CameraDirector', () => {
  it('maps keys 1-6 to presets and reports media time', () => {
    const d = makeDirector();
    let now = 18291;
    d.setClock(() => now);
    const cuts: Array<{ preset: string; ms: number }> = [];
    d.setOnCut((preset, ms) => cuts.push({ preset, ms }));

    expect(d.handleKeyboard('2')).toBe(true);
    expect(d.getCurrentPreset()).toBe('COMIC_MEDIUM');
    now = 19022;
    expect(d.handleKeyboard('3')).toBe(true);
    expect(d.getCurrentPreset()).toBe('COMIC_CLOSE');
    expect(cuts).toEqual([
      { preset: 'COMIC_MEDIUM', ms: 18291 },
      { preset: 'COMIC_CLOSE', ms: 19022 },
    ]);
    // Cutting to the active preset is a no-op (no duplicate events)
    d.handleKeyboard('3');
    expect(cuts).toHaveLength(2);
  });

  it('rejects invalid keys without side effects', () => {
    const d = makeDirector();
    const cuts: string[] = [];
    d.setOnCut((preset) => cuts.push(preset));
    expect(d.handleKeyboard('x')).toBe(false);
    expect(d.handleKeyboard('2')).toBe(true); // '2' is valid (COMIC_MEDIUM)
    expect(d.getCurrentPreset()).toBe('COMIC_MEDIUM');
    expect(cuts).toHaveLength(1);
  });

  it('cut() applies the preset to the camera', () => {
    const d = makeDirector();
    d.cut('COMIC_CLOSE');
    const data = d.getPresetData('COMIC_CLOSE');
    expect(data.fov).toBe(28);
  });

  it('maps judge closeups on keys 7-8', () => {
    const d = makeDirector();
    expect(d.handleKeyboard('7')).toBe(true);
    expect(d.getCurrentPreset()).toBe('CHATGPT_CLOSE');
    expect(d.handleKeyboard('8')).toBe(true);
    expect(d.getCurrentPreset()).toBe('STREAM_CLOSE');
  });

  it('bindKeyboard returns an unbind function that removes the listener', () => {
    const added: Array<[string, unknown]> = [];
    const removed: Array<[string, unknown]> = [];
    vi.stubGlobal('window', {
      addEventListener: (t: string, h: unknown) => { added.push([t, h]); },
      removeEventListener: (t: string, h: unknown) => { removed.push([t, h]); },
    });
    const d = makeDirector();
    const unbind = d.bindKeyboard();
    expect(added).toHaveLength(1);
    unbind();
    expect(removed).toHaveLength(1);
    expect(removed[0][1]).toBe(added[0][1]);
  });
});
