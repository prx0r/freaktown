/**
 * FaceChannel — the one place a body's face is composed, per performer:
 *
 *   base   Performer emotions/blink + plan/text mouth (as before)
 *   affect optional A/V/P hold (face.affect) → emotions, max-blended
 *   live   optional ARKit-52 stream (face.blendshapes, e.g. MediaPipe on a phone):
 *          overrides mouth + blink while fresh (staleMs), emotions max-blended
 *
 * apply(driver, frame) writes the frame through the AvatarDriver interface:
 * setMouth/setExpression/setBlink for every tier, plus setBlendshapes() with raw
 * ARKit weights for drivers whose bytes carry them (GLB morphs, VRM custom
 * expressions, BASIC asymmetric brows/mouth). Channels never clear each other.
 */
import type { AvatarDriver, Emotions, Visemes } from '../avatars/types';
import { arkitToFace, faceToArkit, type Blendshapes, type FaceFrame } from './arkit';
import { affectToEmotions } from './affect';
import { channelsFromState } from './expressive';

export interface FaceChannelOptions { staleMs?: number; smoothing?: number }

const EMO_KEYS: (keyof Emotions)[] = ['happy', 'angry', 'sad', 'surprised', 'relaxed'];

export class FaceChannel {
  private live: { frame: FaceFrame; at: number } | null = null;
  private affect: { emotions: Emotions; until: number; weight: number } | null = null;
  private smooth: FaceFrame | null = null;
  private opts: Required<FaceChannelOptions>;
  /** Telemetry: which layers fed the last frame. */
  sources: string[] = [];

  constructor(opts: FaceChannelOptions = {}) { this.opts = { staleMs: 450, smoothing: 0.5, ...opts }; }

  setBlendshapes(weights: Blendshapes, now: number): void {
    this.live = { frame: arkitToFace(weights), at: now };
  }
  setAffect(a: number, v: number, p: number, now: number, holdMs = 4000, weight = 0.8): void {
    this.affect = { emotions: affectToEmotions(a, v, p), until: now + holdMs, weight };
  }
  clear(): void { this.live = null; this.affect = null; this.smooth = null; }

  get liveActive(): boolean { return !!this.live; }

  sample(now: number, base: { open: number; visemes: Visemes; emotions: Emotions; blink: number }): FaceFrame {
    const out: FaceFrame = { open: base.open, visemes: { ...base.visemes }, emotions: { ...base.emotions }, blink: base.blink };
    this.sources = ['base'];
    if (this.affect) {
      if (now > this.affect.until) this.affect = null;
      else {
        for (const k of EMO_KEYS) out.emotions[k] = Math.max(out.emotions[k], this.affect.emotions[k] * this.affect.weight);
        this.sources.push('affect');
      }
    }
    if (this.live) {
      if (now - this.live.at > this.opts.staleMs) { this.live = null; this.smooth = null; }
      else {
        const l = this.live.frame;
        const s = this.opts.smoothing;
        const prev = this.smooth ?? l;
        const mix = (a: number, b: number) => a + (b - a) * (1 - s);
        const sm: FaceFrame = {
          open: mix(prev.open, l.open), blink: l.blink, blendshapes: l.blendshapes,
          visemes: { aa: mix(prev.visemes.aa, l.visemes.aa), ih: mix(prev.visemes.ih, l.visemes.ih), ou: mix(prev.visemes.ou, l.visemes.ou), ee: mix(prev.visemes.ee, l.visemes.ee), oh: mix(prev.visemes.oh, l.visemes.oh) },
          emotions: { ...l.emotions },
        };
        this.smooth = sm;
        // a speaking plan mouth wins over a closed live mouth; otherwise live drives
        if (sm.open >= base.open * 0.8) { out.open = sm.open; out.visemes = sm.visemes; }
        for (const k of EMO_KEYS) out.emotions[k] = Math.max(out.emotions[k], sm.emotions[k]);
        out.blink = sm.blink;
        out.blendshapes = sm.blendshapes;
        this.sources.push('live');
      }
    }
    return out;
  }

  /** Write a frame through the driver. ARKit weights go to drivers that carry them. */
  static apply(driver: AvatarDriver, f: FaceFrame): void {
    driver.setExpression(f.emotions);
    driver.setMouth(f.open, f.visemes);
    driver.setBlink(f.blink);
    if (driver.setBlendshapes) {
      // live ARKit when present; otherwise our plan face re-expressed in ARKit
      // (lets ARKit-only GLBs perform text/plan mouths and emotion cues)
      driver.setBlendshapes(f.blendshapes ?? faceToArkit(f));
    }
    if (driver.setExpressive) driver.setExpressive(FaceChannel.expressive(f));
  }

  /** The frame as expressive channels (expressive-map.json) — what the Blender bake keys for the same frame. */
  static expressive(f: FaceFrame) {
    const x = f.expressive ?? {};
    return channelsFromState({
      open: f.open, visemes: f.visemes, emotions: f.emotions,
      blinkL: Math.max(f.blink, x.blinkL ?? 0), blinkR: Math.max(f.blink, x.blinkR ?? 0),
      browUp: x.browUp, browDown: x.browDown, squint: x.squint, smirk: x.smirk, lookX: x.lookX, lookY: x.lookY,
      speaking: f.open > 0.05,
    });
  }
}
