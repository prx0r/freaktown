/**
 * SetEventExecutor — room events → SetStage, strictly in seq order.
 *   set.load {setId, cast?}      build the set (+ cast)
 *   set.cast {cast}              (re)fill seats
 *   set.camera {cue}             seat-aware cut ("close:seat2", "two-shot:host+guest", "wide", "auto")
 *   camera.cut {camera}          accepted too when the camera is a cue of this set
 *   set.auto_director {on}
 *   dialogue.line {seat,text}    speaker mouth + auto cut (skipped on replay once it's over)
 *   overlay.lower_third / overlay.ticker / overlay.headline (+ wall card fields: layout/body/figure/credit)
 *   set.theme {style, palette, lighting…}   show style (newsroom)
 *   set.camera {cue, move_ms?, creep?}      eased move / slow push-in (newsroom)
 *   seat.join {seat,name,avatar_url}  a human/bot takes a seat (BASIC by default)
 *   poker.*                      cards / chips / reactions
 *   gaze.look {seat,target,duration_ms}   scripted look (sketch) — overrides "listeners watch the speaker"
 *   stage.move {seat,to,duration_ms}      walk to another seat/mark (sketch move-to)
 *   overlay.blackout {on,fade_ms}         fade to black (sketch ending)
 */
import type { SetThemePayloadV1, ShowEvent } from '@funnier/contracts';
import type { EventConsumer } from '../EventConsumer';
import type { SetStage } from './SetStage';
import { estimateLineMs } from './textMouth';

export interface SetExecutorOptions { onError?: (m: string) => void; now?: () => number }

export class SetEventExecutor {
  private queue: Promise<void> = Promise.resolve();
  private off: (() => void) | null = null;
  readonly executed: Array<{ seq: number; type: string }> = [];

  constructor(private stage: SetStage, private consumer: EventConsumer, private opts: SetExecutorOptions = {}) {}

  attach(): void {
    this.off = this.consumer.onEvent((e) => {
      this.queue = this.queue.then(() => this.execute(e)).catch((err: unknown) => this.opts.onError?.(err instanceof Error ? err.message : String(err)));
    });
  }
  detach(): void { this.off?.(); this.off = null; }

  async execute(event: ShowEvent): Promise<void> {
    const p = event.payload ?? {};
    const s = this.stage;
    switch (event.type) {
      case 'set.load':
        await s.loadSet(String(p.setId), Array.isArray(p.cast) ? p.cast : []);
        break;
      case 'set.cast':
        if (Array.isArray(p.cast)) await s.cast(p.cast);
        break;
      case 'seat.join': {
        const def = s.definition;
        const seat = def?.seats[Number(p.seat)];
        if (seat) await s.cast([{ seat: seat.id, character_id: `human.${p.name}`, name: String(p.name ?? 'Player'), avatar_url: p.avatar_url ?? 'basic', kind: p.kind ?? 'human' }]);
        break;
      }
      case 'set.camera':
        if (typeof p.cue === 'string') s.cut(p.cue, p.source === 'auto_director' ? 'auto_director' : 'human_director', { move_ms: p.move_ms, ease: p.ease, creep: p.creep, creep_ms: p.creep_ms });
        break;
      case 'camera.cut':
        if (typeof p.camera === 'string' && s.definition && !/^[A-Z_]+$/.test(p.camera)) s.cut(p.camera, 'human_director');
        break;
      case 'set.auto_director':
        s.setAutoDirector(p.on !== false);
        break;
      case 'dialogue.line': {
        const dur = Number(p.duration_ms ?? estimateLineMs(String(p.text ?? '')));
        const age = this.ageMs(event);
        if (age !== null && age > dur + 1000) break; // replay: the line is over
        s.say({ seat: String(p.seat), text: String(p.text ?? ''), duration_ms: dur, audio_url: p.audio_url, cue: p.cue, emotion: p.emotion, words: p.words, beats: p.beats });
        break;
      }
      case 'face.expression':
        s.faceExpression(p);
        break;
      case 'face.blendshapes':
        if (p.weights && typeof p.weights === 'object') s.faceBlendshapes(p.seat, p.weights);
        break;
      case 'face.affect':
        s.faceAffect({ seat: p.seat, a: Number(p.a ?? 0), v: Number(p.v ?? 0), p: Number(p.p ?? 0), hold_ms: p.hold_ms });
        break;
      case 'overlay.lower_third':
        s.lowerThird({ name: String(p.name ?? ''), title: p.title, show: p.show });
        break;
      case 'overlay.ticker':
        s.ticker(Array.isArray(p.items) ? p.items.map(String) : []);
        break;
      case 'overlay.headline':
        s.headline(String(p.text ?? ''), p.kicker, p.layout || p.body || p.figure || p.credit ? { layout: p.layout, body: p.body, figure: p.figure, credit: p.credit, image_url: p.image_url, image_license: p.image_license } : undefined);
        break;
      case 'gaze.look':
        if (typeof p.seat === 'string' && p.target) s.look({ seat: p.seat, target: p.target, duration_ms: Number(p.duration_ms ?? 1200), snap: p.snap });
        break;
      case 'stage.move':
        if (typeof p.seat === 'string' && typeof p.to === 'string') s.moveTo({ seat: p.seat, to: p.to, duration_ms: Number(p.duration_ms ?? 1200) });
        break;
      case 'overlay.blackout':
        s.blackout({ on: p.on !== false, fade_ms: p.fade_ms });
        break;
      case 'set.theme':
        if (typeof p.style === 'string') s.theme(p as SetThemePayloadV1);
        break;
      default:
        if (event.type.startsWith('poker.') && event.type !== 'poker.intent') s.poker(event.type, p);
        else return;
    }
    this.executed.push({ seq: event.seq, type: event.type });
  }

  private ageMs(e: ShowEvent): number | null {
    if (!e.created_at) return null;
    const t = Date.parse(e.created_at);
    if (!Number.isFinite(t)) return null;
    return (this.opts.now?.() ?? Date.now()) - t;
  }
}
