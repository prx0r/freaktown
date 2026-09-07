/**
 * AudioBus — four-channel audio mixing for the stage.
 *
 * VOICE — comedian speech
 * MUSIC — walkout music, stings
 * SFX   — rimshots, bombs, crowd effects
 * CROWD — live audience audio (future)
 *
 * Each channel is a GainNode for volume control.
 * Ducking: music ramps down when comedian starts speaking.
 */

export type AudioChannel = 'VOICE' | 'MUSIC' | 'SFX' | 'CROWD';

export class AudioBus {
  private context: AudioContext;
  private channels: Map<AudioChannel, GainNode> = new Map();
  private destinations: Map<AudioChannel, AudioNode> = new Map();

  constructor(context: AudioContext) {
    this.context = context;

    // Create gain nodes for each channel
    const channelNames: AudioChannel[] = ['VOICE', 'MUSIC', 'SFX', 'CROWD'];
    for (const name of channelNames) {
      const gain = context.createGain();
      gain.connect(context.destination);
      this.channels.set(name, gain);
    }
  }

  // ── Channel Control ──────────────────────────────────────────────

  getGain(channel: AudioChannel): GainNode {
    return this.channels.get(channel)!;
  }

  setVolume(channel: AudioChannel, volume: number): void {
    const gain = this.channels.get(channel);
    if (gain) {
      gain.gain.setValueAtTime(Math.max(0, Math.min(1, volume)), this.context.currentTime);
    }
  }

  rampVolume(channel: AudioChannel, target: number, durationMs: number): void {
    const gain = this.channels.get(channel);
    if (gain) {
      const now = this.context.currentTime;
      gain.gain.linearRampToValueAtTime(
        Math.max(0, Math.min(1, target)),
        now + durationMs / 1000
      );
    }
  }

  // ── Convenience Methods ──────────────────────────────────────────

  /**
   * Play audio on a specific channel.
   * Returns the source node for external control.
   */
  async playUrl(channel: AudioChannel, url: string): Promise<AudioBufferSourceNode> {
    const response = await fetch(url);
    const buffer = await this.context.decodeAudioData(await response.arrayBuffer());
    return this.playBuffer(channel, buffer);
  }

  playBuffer(channel: AudioChannel, buffer: AudioBuffer): AudioBufferSourceNode {
    const source = this.context.createBufferSource();
    source.buffer = buffer;

    const gain = this.channels.get(channel);
    if (gain) {
      source.connect(gain);
    } else {
      source.connect(this.context.destination);
    }

    source.start(0);
    return source;
  }

  /**
   * Duck music channel when voice starts.
   * Ramp music from current to 0.2 over 300ms.
   */
  duckMusic(): void {
    this.rampVolume('MUSIC', 0.2, 300);
  }

  /**
   * Restore music channel after voice ends.
   * Ramp music from current to 1.0 over 500ms.
   */
  unduckMusic(): void {
    this.rampVolume('MUSIC', 1.0, 500);
  }

  /**
   * Mute all channels.
   */
  muteAll(): void {
    for (const gain of this.channels.values()) {
      gain.gain.setValueAtTime(0, this.context.currentTime);
    }
  }

  /**
   * Restore all channels to default volumes.
   */
  unmuteAll(): void {
    this.setVolume('VOICE', 1.0);
    this.setVolume('MUSIC', 0.8);
    this.setVolume('SFX', 0.6);
    this.setVolume('CROWD', 0.5);
  }

  // ── Cleanup ──────────────────────────────────────────────────────

  dispose(): void {
    for (const gain of this.channels.values()) {
      gain.disconnect();
    }
    this.channels.clear();
  }
}
