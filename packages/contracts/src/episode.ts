// Pure EpisodeRoom state transition — the ONE copy. The Durable Object
// (edge/worker/episode-room.ts) and the offline LocalRoom both call this,
// so local mode and Cloudflare mode can never disagree on show state.

export type EpisodeState = {
  episodeId: string;
  phase: string;
  activeAppearanceId: string | null;
  seq: number;
  startedAt: string | null;
  isPaused: boolean;
};

export function initialEpisodeState(episodeId = ""): EpisodeState {
  return {
    episodeId,
    phase: "pre_show",
    activeAppearanceId: null,
    seq: 0,
    startedAt: null,
    isPaused: false,
  };
}

/** Mutates and returns `state` (DO style) for an already-sequenced event. */
export function applyEpisodeEvent(
  state: EpisodeState,
  type: string,
  payload: Record<string, unknown>,
  nowIso: string = new Date().toISOString(),
): EpisodeState {
  switch (type) {
    case "show.start":
      state.phase = "intro";
      state.startedAt = nowIso;
      break;
    case "show.phase":
    case "phase.change":
      if (typeof payload.phase === "string") state.phase = payload.phase;
      break;
    case "character.enter":
      if (typeof payload.appearanceId === "string") {
        state.activeAppearanceId = payload.appearanceId;
      }
      break;
    case "character.exit":
      state.activeAppearanceId = null;
      break;
    case "show.pause":
      state.isPaused = true;
      break;
    case "show.resume":
      state.isPaused = false;
      break;
    case "show.end":
      state.phase = "ended";
      break;
    default:
      break;
  }
  return state;
}
