/**
 * Ports — what the runtime needs from its host, injected (README debt #1/#2).
 *
 * The runtime never imports app state. Apps hand it:
 *   - ClockSink: receives the media clock every frame (e.g. a zustand
 *     setter for a timer readout).
 *   - RoomStore: a pure mirror of room state the EventConsumer feeds.
 *     apps/live wires its zustand showStore; tests use createMemoryRoomStore.
 */

import type { ShowEvent, ShowPhase } from '@funnier/contracts';

export interface ClockSink {
  setCurrentTime(ms: number): void;
}

export const NULL_CLOCK_SINK: ClockSink = { setCurrentTime: () => {} };

export interface RoomCrowd {
  active_viewers?: number;
  unique_laughers?: number;
  laugh_events?: number;
  claps?: number;
  boos?: number;
  crickets?: number;
  groans?: number;
}

export interface RoomStore {
  /** Idempotent by seq: duplicate/replayed events never apply twice. */
  applyEvent(event: ShowEvent): void;
  setEpisode(episodeId: string): void;
  setPhase(phase: ShowPhase): void;
  setCrowd(crowd: RoomCrowd): void;
}

export interface MemoryRoomState {
  episodeId: string | null;
  phase: ShowPhase;
  isPaused: boolean;
  events: ShowEvent[];
  lastSeq: number;
  crowd: RoomCrowd;
  camera: string | null;
}

/** Minimal in-memory RoomStore (tests, headless tools). */
export function createMemoryRoomStore(): RoomStore & { state: MemoryRoomState } {
  const state: MemoryRoomState = {
    episodeId: null, phase: 'pre_show', isPaused: false,
    events: [], lastSeq: 0, crowd: {}, camera: null,
  };
  return {
    state,
    applyEvent(event) {
      if (event.seq <= state.lastSeq) return;
      state.events.push(event);
      state.lastSeq = event.seq;
      const p = event.payload ?? {};
      switch (event.type) {
        case 'show.start': state.phase = 'intro'; break;
        case 'show.pause': state.isPaused = true; break;
        case 'show.resume': state.isPaused = false; break;
        case 'show.end': state.phase = 'ended'; break;
        case 'show.phase':
        case 'phase.change': if (typeof p.phase === 'string') state.phase = p.phase as ShowPhase; break;
        case 'character.enter': state.phase = 'set_active'; break;
        case 'character.exit': state.phase = 'post_set'; break;
        case 'camera.cut': if (typeof p.camera === 'string') state.camera = p.camera; break;
        default: break;
      }
    },
    setEpisode(id) { state.episodeId = id; },
    setPhase(phase) { state.phase = phase; },
    setCrowd(c) { state.crowd = { ...state.crowd, ...c }; },
  };
}
