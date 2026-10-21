/**
 * SfxSynth — procedural crowd/sting sounds on the SFX bus (no assets, $0).
 * laugh · clap · boo · groan · crickets · rimshot. Approximate, honest:
 * a stand-in until the sound bank (sound_bank.py) ships real samples.
 */

export type SfxName = 'laugh' | 'clap' | 'boo' | 'groan' | 'crickets' | 'rimshot' | 'love' | 'wtf';

function noiseBuffer(ctx: BaseAudioContext, seconds: number): AudioBuffer {
  const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * seconds), ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  return buf;
}

export class SfxSynth {
  private ctx: AudioContext;
  private out: AudioNode;
  private noise: AudioBuffer;

  constructor(ctx: AudioContext, out: AudioNode) {
    this.ctx = ctx;
    this.out = out;
    this.noise = noiseBuffer(ctx, 2);
  }

  play(name: string): void {
    const t = this.ctx.currentTime + 0.01;
    switch (name) {
      case 'laugh': case 'love': return this.laugh(t);
      case 'clap': return this.clap(t);
      case 'boo': return this.tone(t, 'sawtooth', 140, 110, 1.4, 0.18, 6);
      case 'groan': return this.tone(t, 'sawtooth', 190, 120, 1.1, 0.15, 3);
      case 'crickets': return this.crickets(t);
      case 'rimshot': case 'wtf': return this.rimshot(t);
      default: return;
    }
  }

  private noiseBurst(t: number, dur: number, freq: number, q: number, gain: number): void {
    const src = this.ctx.createBufferSource();
    src.buffer = this.noise;
    const f = this.ctx.createBiquadFilter();
    f.type = 'bandpass'; f.frequency.value = freq; f.Q.value = q;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(gain, t + Math.min(0.01, dur / 4));
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
    src.connect(f).connect(g).connect(this.out);
    src.start(t, Math.random() * 1.5, dur + 0.05);
  }

  private laugh(t: number): void {
    // several "voices": vowel-ish bandpassed noise pulsed at ~5 Hz
    for (let v = 0; v < 7; v++) {
      const start = t + Math.random() * 0.35;
      const rate = 4.2 + Math.random() * 2.2;
      const formant = 500 + Math.random() * 700;
      const pulses = 6 + Math.floor(Math.random() * 6);
      for (let i = 0; i < pulses; i++) {
        const decay = 1 - i / (pulses + 2);
        this.noiseBurst(start + i / rate, 0.12, formant * (1 - i * 0.02), 4, 0.22 * decay);
      }
    }
  }

  private clap(t: number): void {
    for (let i = 0; i < 70; i++) {
      this.noiseBurst(t + Math.random() * 1.8, 0.05, 1200 + Math.random() * 1500, 1.2, 0.18 * (1 - i / 90));
    }
  }

  private crickets(t: number): void {
    for (let i = 0; i < 10; i++) {
      const o = this.ctx.createOscillator();
      o.frequency.value = 4400;
      const g = this.ctx.createGain();
      const st = t + Math.floor(i / 3) * 0.6 + (i % 3) * 0.07;
      g.gain.setValueAtTime(0, st);
      g.gain.linearRampToValueAtTime(0.05, st + 0.01);
      g.gain.linearRampToValueAtTime(0, st + 0.05);
      o.connect(g).connect(this.out);
      o.start(st); o.stop(st + 0.06);
    }
  }

  private tone(t: number, type: OscillatorType, f0: number, f1: number, dur: number, gain: number, vib: number): void {
    for (let v = 0; v < 4; v++) {
      const o = this.ctx.createOscillator();
      o.type = type;
      o.frequency.setValueAtTime(f0 * (1 + v * 0.03), t);
      o.frequency.linearRampToValueAtTime(f1 * (1 + v * 0.02), t + dur);
      const lfo = this.ctx.createOscillator();
      lfo.frequency.value = vib;
      const lg = this.ctx.createGain();
      lg.gain.value = 6;
      lfo.connect(lg).connect(o.frequency);
      const lp = this.ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 900;
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0, t);
      g.gain.linearRampToValueAtTime(gain / 4, t + 0.15);
      g.gain.linearRampToValueAtTime(0, t + dur);
      o.connect(lp).connect(g).connect(this.out);
      o.start(t); lfo.start(t); o.stop(t + dur + 0.05); lfo.stop(t + dur + 0.05);
    }
  }

  private rimshot(t: number): void {
    const kick = (when: number) => {
      const o = this.ctx.createOscillator();
      o.frequency.setValueAtTime(180, when);
      o.frequency.exponentialRampToValueAtTime(60, when + 0.12);
      const g = this.ctx.createGain();
      g.gain.setValueAtTime(0.5, when);
      g.gain.exponentialRampToValueAtTime(0.001, when + 0.15);
      o.connect(g).connect(this.out);
      o.start(when); o.stop(when + 0.16);
    };
    kick(t); this.noiseBurst(t, 0.12, 2500, 1, 0.3);
    kick(t + 0.18); this.noiseBurst(t + 0.18, 0.1, 2500, 1, 0.25);
    this.noiseBurst(t + 0.42, 0.9, 6000, 0.7, 0.18);
  }
}
