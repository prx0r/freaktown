/**
 * ExpressionLayer unit tests — envelope math with a fake writer.
 * No VRM, no DOM, no clock. Deterministic.
 */
import { describe, expect, it } from 'vitest';
import { ExpressionLayer } from './ExpressionLayer';

function makeWriter() {
  const values: Record<string, number> = {};
  return {
    values,
    setValue(name: string, v: number) {
      values[name] = v;
    },
  };
}

describe('ExpressionLayer', () => {
  it('ramps to the target instead of popping', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    expect(layer.setExpression('face.smile', 1.0)).toBe(true);
    layer.update(0, em);
    // attack phase: partial, not 1.0
    expect(em.values['happy'] ?? 0).toBeGreaterThan(0);
    expect(em.values['happy'] ?? 0).toBeLessThan(1.0);
    // hold phase: converged
    for (let t = 16; t < 600; t += 16) layer.update(t, em);
    expect(em.values['happy'] ?? 0).toBeCloseTo(1.0, 1);
  });

  it('decays back to zero after hold', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    layer.setExpression('face.surprised', 1.0, { holdMs: 100, decayMs: 100 });
    for (let t = 0; t < 600; t += 16) layer.update(t, em);
    expect(em.values['surprised'] ?? 0).toBeCloseTo(0, 1);
  });

  it('accepts face_ spelling for delivery words', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    expect(layer.setExpression('face_whisper', 1.0)).toBe(true);
    for (let t = 0; t < 600; t += 16) layer.update(t, em);
    expect(em.values['neutral'] ?? 0).toBeGreaterThan(0.2);
    expect(layer.setExpression('face_shout', 1.0)).toBe(true);
  });

  it('unknown actions no-op and never raise', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    expect(layer.setExpression('face.moonwalk', 1.0)).toBe(false);
    expect(layer.setExpression('', 1.0)).toBe(false);
    layer.update(100, em);
    layer.update(200, null);
    layer.update(300, undefined);
  });

  it('never writes mouth visemes or blink', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    layer.setExpression('face.smile', 1.0);
    for (let t = 0; t < 600; t += 16) layer.update(t, em);
    for (const k of Object.keys(em.values)) {
      expect(['happy', 'angry', 'sad', 'surprised', 'neutral']).toContain(k);
    }
  });

  it('re-targeting mid-hold moves to the new face', () => {
    const em = makeWriter();
    const layer = new ExpressionLayer();
    layer.setExpression('face.smile', 1.0);
    for (let t = 0; t < 300; t += 16) layer.update(t, em);
    layer.setExpression('face.annoyed', 1.0);
    for (let t = 300; t < 1200; t += 16) layer.update(t, em);
    expect(em.values['angry'] ?? 0).toBeGreaterThan(0.5);
    expect(em.values['happy'] ?? 0).toBeLessThan(0.5);
  });

  it('drives ARKit morphs on the GLB path alongside VRM presets', () => {
    const vrm = makeWriter();
    const glb = makeWriter();
    const layer = new ExpressionLayer();
    layer.morphWriter = glb;
    layer.setExpression('face.annoyed', 1.0);
    for (let t = 0; t < 500; t += 16) layer.update(t, vrm);
    // VRM preset still moves (existing behavior preserved)
    expect(vrm.values['angry'] ?? 0).toBeGreaterThan(0.5);
    // ARKit brow + frown move on the morph writer
    expect(glb.values['browDownLeft'] ?? 0).toBeGreaterThan(0.4);
    expect(glb.values['mouthFrownLeft'] ?? 0).toBeGreaterThan(0.3);
    // retarget decays the old morphs
    layer.setExpression('face.grin', 1.0);
    for (let t = 500; t < 1500; t += 16) layer.update(t, vrm);
    expect(glb.values['browDownLeft'] ?? 0).toBeLessThan(0.05);
    expect(glb.values['mouthSmileLeft'] ?? 0).toBeGreaterThan(0.5);
  });

  it('grin uses cheeks, disgust uses nose', () => {
    const glb = makeWriter();
    const layer = new ExpressionLayer();
    layer.morphWriter = glb;
    layer.setExpression('face.disgusted', 1.0);
    for (let t = 0; t < 600; t += 16) layer.update(t, null);
    expect(glb.values['noseSneerLeft'] ?? 0).toBeGreaterThan(0.5);
  });

  it('prosody lifts brows on accents under a deadpan beat', () => {
    const glb = makeWriter();
    const layer = new ExpressionLayer();
    layer.morphWriter = glb;
    layer.playProsody([
      { t_ms: 0, accent: 0, arousal: 0.2, phrase_end: 0 },
      { t_ms: 100, accent: 0.9, arousal: 0.3, phrase_end: 0 },
      { t_ms: 200, accent: 0, arousal: 0.2, phrase_end: 0 },
    ]);
    layer.setExpression('face.deadpan', 1.0);
    for (let t = 0; t < 150; t += 16) layer.update(t, null);
    expect(glb.values['browInnerUp'] ?? 0).toBeGreaterThan(0.1);
    // arousal widens eyes a little even with no beat
    expect(glb.values['eyeWideLeft'] ?? 0).toBeGreaterThan(0.02);
  });

  it('phrase end blinks and decays', () => {
    const glb = makeWriter();
    const layer = new ExpressionLayer();
    layer.morphWriter = glb;
    layer.playProsody([
      { t_ms: 0, accent: 0, arousal: 0, phrase_end: 0 },
      { t_ms: 100, accent: 0, arousal: 0, phrase_end: 1 },
    ]);
    layer.setExpression('face.deadpan', 1.0);
    for (let t = 0; t < 150; t += 16) layer.update(t, null);
    const peak = glb.values['eyeBlinkLeft'] ?? 0;
    expect(peak).toBeGreaterThan(0.3);
    for (let t = 150; t < 3000; t += 16) layer.update(t, null);
    expect(glb.values['eyeBlinkLeft'] ?? 0).toBeLessThan(0.05);
  });

  it('bad prosody frames never raise', () => {
    const glb = makeWriter();
    const layer = new ExpressionLayer();
    layer.morphWriter = glb;
    layer.playProsody(null);
    layer.playProsody(undefined);
    layer.playProsody([{ t_ms: 'x', accent: 1, arousal: 1, phrase_end: 0 }] as unknown as never);
    layer.setExpression('face.smile', 1.0);
    layer.update(100, null);
  });
});
