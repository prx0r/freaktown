import { describe, expect, it } from 'vitest';
import * as THREE from 'three';
import {
  ARKIT_52, OCULUS_TO_VRM, oculusToVisemes, arkitToFace, smileFusion, faceToArkit,
  affectToDelivery, affectToEmotions, normalizeFaceAction, emotionToFaceAction,
  compileHarnessBeats, FaceChannel,
} from '../src/face';
import { Performer } from '../src/performance/Performer';
import { BasicAvatar } from '../src/avatars/BasicAvatar';
import { GlbAvatar } from '../src/avatars/GlbAvatar';
import { adaptSealedSet } from '../src/plan/setAdapter';

describe('ARKit / Oculus / VRM maps (ported from mutuals-acting-party-smiles)', () => {
  it('has the 52 ARKit names and the WAWA Oculus-15 → VRM-5 table', () => {
    expect(ARKIT_52).toHaveLength(52);
    expect(new Set(ARKIT_52).size).toBe(52);
    expect(Object.keys(OCULUS_TO_VRM)).toHaveLength(15);
    expect(oculusToVisemes('viseme_aa').visemes.aa).toBe(1);
    expect(oculusToVisemes('PP').visemes.ou).toBe(0.5);
    expect(oculusToVisemes('sil').open).toBe(0);
  });
  it('arkitToFace: jaw/funnel/pucker → visemes, smile/brows → emotions, blink', () => {
    const f = arkitToFace({ jawOpen: 0.8, mouthSmileLeft: 0.9, mouthSmileRight: 0.9, cheekSquintLeft: 0.6, cheekSquintRight: 0.6, eyeBlinkLeft: 1 });
    expect(f.open).toBeCloseTo(0.8);
    expect(f.visemes.aa).toBeGreaterThan(0.5);
    expect(f.emotions.happy).toBeGreaterThan(0.5);
    expect(f.blink).toBe(1);
    const o = arkitToFace({ jawOpen: 0.3, mouthFunnel: 0.9 });
    expect(o.visemes.oh).toBeGreaterThan(o.visemes.aa);
    const s = arkitToFace({ browInnerUp: 1, eyeWideLeft: 1, eyeWideRight: 1 });
    expect(s.emotions.surprised).toBeGreaterThan(0.9);
    const vrmNamed = arkitToFace({ aa: 0.7, ee: 0.2 }); // MediaPipe on a VRM-named rig
    expect(vrmNamed.visemes.aa).toBeCloseTo(0.7);
  });
  it('smileFusion matches static/affect-servo.js', () => {
    expect(smileFusion({ mouthSmileLeft: 0.8, mouthSmileRight: 0.6, cheekSquintLeft: 0.5, cheekSquintRight: 0.4, eyeSquintLeft: 0.3, eyeSquintRight: 0.3, jawOpen: 0.2 })).toBe(0.448);
    expect(smileFusion({})).toBe(0);
  });
  it('faceToArkit round-trips the dominant channels', () => {
    const a = faceToArkit({ open: 0.6, visemes: { aa: 0.6, ih: 0, ou: 0, ee: 0, oh: 0 }, emotions: { happy: 1, angry: 0, sad: 0, surprised: 0, relaxed: 0 }, blink: 0 });
    const back = arkitToFace(a);
    expect(back.emotions.happy).toBeGreaterThan(0.4);
    expect(back.open).toBeGreaterThan(0.4);
  });
});

describe('affect servo', () => {
  it('affectToDelivery matches static/affect-servo.js', () => {
    expect(affectToDelivery(0.9, 0.5, 0.2)).toEqual({ energy: 1, pace: 1.192, pauseMs: 450, emphasis: 0.56, hot: true });
    expect(affectToDelivery(-0.5, -0.3, 0.8)).toEqual({ energy: 0.345, pace: 0.892, pauseMs: 1105, emphasis: 0.74, hot: false });
  });
  it('affectToEmotions projects A/V/P onto VRM emotions', () => {
    expect(affectToEmotions(0.2, 0.9).happy).toBeGreaterThan(0.7);
    const angry = affectToEmotions(0.8, -0.8, 0.6);
    expect(angry.angry).toBeGreaterThan(angry.sad);
    const sad = affectToEmotions(-0.6, -0.8, -0.3);
    expect(sad.sad).toBeGreaterThan(sad.angry);
    expect(affectToEmotions(1, 0).surprised).toBeGreaterThan(0.5);
  });
});

describe('acting vocabulary + harness beats', () => {
  it('normalizes aliases and bare emotions', () => {
    expect(normalizeFaceAction('face_excited')).toBe('face.smile');
    expect(normalizeFaceAction('reaction.smile')).toBe('face.smile');
    expect(normalizeFaceAction('smug')).toBe('face.smug');
    expect(normalizeFaceAction('lean_in')).toBe('gesture.lean');
    expect(normalizeFaceAction('gesture.open')).toBe('gesture.open');
    expect(emotionToFaceAction('deadpan')).toBe('face.deadpan');
    expect(emotionToFaceAction('wave')).toBeNull();
  });
  it('Performer renders aliased face cues (face_excited → happy)', () => {
    const p = new Performer();
    p.trigger('face_excited', 1, 2000, 0);
    const f = p.update(800, 800, 0.016, 0);
    expect(f.emotions.happy).toBeGreaterThan(0.5);
  });
  const text = 'I trained a robot to love me. It filed a complaint.';
  const words = text.split(' ').map((w, i) => ({ word: w, start_ms: i * 300, end_ms: i * 300 + 250 }));
  it('compiles beats onto measured word onsets (port of compile_harness_beats)', () => {
    const r = compileHarnessBeats(text, [
      { span: 'I trained', emotion: 'smug', gesture: 'shrug' },
      { span: 'It filed', emotion: 'deadpan', camera: 'push-in' },
    ], words);
    expect(r.motion.map((m) => [m.at_ms, m.action])).toEqual([[0, 'face.smug'], [0, 'gesture.shrug'], [2100, 'face.deadpan']]);
    expect(r.camera).toEqual([{ at_ms: 2100, camera: 'COMIC_CLOSE' }]);
    expect(r.source).toBe('mutuals-beats/v1');
  });
  it('fails closed on mismatch / order and warns on unsupported', () => {
    expect(() => compileHarnessBeats(text, [], words.slice(1))).toThrow(/alignment/);
    expect(() => compileHarnessBeats(text, [{ span: 'complaint' }, { span: 'robot' }], words)).toThrow(/out of order|span/);
    const r = compileHarnessBeats(text, [{ span: 'robot', emotion: 'sad', gesture: 'moonwalk', camera: 'dolly' }], words, { expressions: ['happy'] });
    expect(r.warnings).toEqual(['unsupported expression: sad', 'unsupported gesture: moonwalk', 'unknown camera: dolly']);
  });
  it('sealed sets: measured words.json + acting.json overlay reach the plan', () => {
    const timeline = [{ beat_id: 'b1', type: 'setup', text, start_ms: 0, end_ms: 3300 }];
    const plan = adaptSealedSet({ timeline: timeline as never, words, acting: { schema: 'mutuals-beats/v1', beats: [{ span: 'It filed', emotion: 'deadpan', camera: 'push-in' }] } });
    expect(plan.source).toMatchObject({ words: 'measured', acting: 'mutuals-beats/v1' });
    expect(plan.word_timings![7].start_ms).toBe(2100);
    expect(plan.cues.some((c) => c.action === 'face.deadpan' && c.at_ms === 2100)).toBe(true);
    expect(plan.camera_cues!.some((c) => c.camera === 'COMIC_CLOSE')).toBe(true);
    const noWords = adaptSealedSet({ timeline: timeline as never, acting: { beats: [{ span: 'It', emotion: 'smug' }] } });
    expect((noWords.source as { acting_warnings: string[] }).acting_warnings[0]).toMatch(/measured words/);
  });
});

describe('FaceChannel', () => {
  const base = { open: 0, visemes: { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 }, emotions: { happy: 0, angry: 0, sad: 0, surprised: 0, relaxed: 0 }, blink: 0 };
  it('live ARKit stream drives mouth/blink while fresh, then goes stale', () => {
    const fc = new FaceChannel({ staleMs: 400, smoothing: 0 });
    fc.setBlendshapes({ jawOpen: 0.9, eyeBlinkLeft: 1, mouthSmileLeft: 1, mouthSmileRight: 1, cheekSquintLeft: 1, cheekSquintRight: 1 }, 1000);
    const f = fc.sample(1100, base);
    expect(f.open).toBeCloseTo(0.9);
    expect(f.blink).toBe(1);
    expect(f.emotions.happy).toBeGreaterThan(0.5);
    expect(fc.sources).toContain('live');
    expect(fc.sample(1600, base).open).toBe(0);
  });
  it('a speaking plan mouth beats a closed live mouth; affect holds then expires', () => {
    const fc = new FaceChannel({ smoothing: 0 });
    fc.setBlendshapes({ jawOpen: 0 }, 0);
    expect(fc.sample(10, { ...base, open: 0.7 }).open).toBe(0.7);
    fc.setAffect(0.2, 0.9, 0, 0, 1000);
    expect(fc.sample(500, base).emotions.happy).toBeGreaterThan(0.5);
    expect(fc.sample(1500, base).emotions.happy).toBe(0);
  });
  it('apply(): BASIC takes the frame + blendshapes; GLB only writes morphs in its bytes', () => {
    const basic = new BasicAvatar({ name: 'b' });
    FaceChannel.apply(basic, arkitToFace({ jawOpen: 0.5, browOuterUpLeft: 1, mouthLeft: 1 }));
    const geo = new THREE.BoxGeometry();
    geo.morphAttributes.position = [geo.attributes.position.clone(), geo.attributes.position.clone()];
    const mesh = new THREE.Mesh(geo, new THREE.MeshBasicMaterial());
    mesh.updateMorphTargets();
    mesh.morphTargetDictionary = { jawOpen: 0, mouthSmileLeft: 1 };
    mesh.morphTargetInfluences = [0, 0];
    const glb = new GlbAvatar(mesh, [], 'arkit-glb');
    glb.setBlendshapes({ jawOpen: 0.6, mouthSmileLeft: 0.4, notInBytes: 1 });
    expect(mesh.morphTargetInfluences).toEqual([0.6, 0.4]);
    expect(glb.caps.mouthMode).toBe('morph');
  });
});
