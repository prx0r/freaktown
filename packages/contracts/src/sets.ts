/**
 * Sets + multi-seat shows (news studio, podcast, poker table, comedy club).
 *
 * Wire types only (dependency-free). The stage chooses a set per episode from
 * the latest `set.load` event; characters are placed in seats with
 * `set.cast`; dialogue, overlays and poker are plain events the stage obeys.
 *
 * Camera cues on a set are strings (see CameraTargetCueV1):
 *   "wide" | "<preset name of the set>" | "close:<seat>" | "single:<seat>"
 *   | "two-shot:<seat>+<seat>" | "overhead" | "orbit" | "auto"
 * where <seat> is a seat id ("seat2", "anchor1"), a role ("host", "guest")
 * or an index ("2").
 */

export type SetIdV1 = "comedy-club" | "news-studio" | "podcast" | "poker-table" | (string & {});

export const SET_EVENT_TYPES = [
  "set.load",
  "set.cast",
  "set.camera",
  "set.auto_director",
  "dialogue.line",
  "overlay.lower_third",
  "overlay.ticker",
  "overlay.headline",
  "poker.hand_start",
  "poker.deal",
  "poker.turn",
  "poker.action",
  "poker.board",
  "poker.chips",
  "poker.showdown",
  "poker.intent",
  "seat.join",
  "seat.leave",
  "face.expression",
  "face.blendshapes",
  "face.affect",
] as const;
export type SetEventTypeV1 = (typeof SET_EVENT_TYPES)[number];

export interface CastMemberV1 {
  seat: string;
  character_id: string;
  name: string;
  /** "basic" | "basic:robot" | avatars/<x>.vrm | any GLB URL. */
  avatar_url?: string;
  /** "bot" (rule policy / script) or "human" (a /play seat). */
  kind?: "bot" | "human" | "character";
}

export interface SetLoadPayloadV1 {
  setId: SetIdV1;
  title?: string;
  cast?: CastMemberV1[];
}

export interface SetCastPayloadV1 {
  cast: CastMemberV1[];
}

export interface SetCameraPayloadV1 {
  /** A camera target cue string (see header). */
  cue: string;
  source?: "human_director" | "auto_director";
}

export interface DialogueLinePayloadV1 {
  seat: string;
  text: string;
  /** Mouth/active-speaker duration when there is no audio. */
  duration_ms?: number;
  audio_url?: string;
  /** Optional face/gesture cue for the speaker ("face.smile", "gesture.point"). */
  cue?: string;
  line_id?: string;
  /** Harness emotion for the whole line ("smug", "deadpan", "excited"). */
  emotion?: string;
  /** Measured word timings relative to the line start (e.g. edge-TTS WordBoundary). */
  words?: Array<{ word: string; start_ms: number; end_ms: number }>;
  /** mutuals-beats/v1 acting beats; applied only with measured `words` (fails closed). */
  beats?: Array<{ span: string; emotion?: string; gesture?: string; camera?: string; register?: string }>;
}

export interface LowerThirdPayloadV1 { name: string; title?: string; show?: boolean }
export interface TickerPayloadV1 { items: string[] }
export interface HeadlinePayloadV1 { text: string; kicker?: string }

// ── poker ───────────────────────────────────────────────────────────

export type CardRankV1 = "2" | "3" | "4" | "5" | "6" | "7" | "8" | "9" | "T" | "J" | "Q" | "K" | "A";
export type CardSuitV1 = "clubs" | "diamonds" | "hearts" | "spades";
export interface CardV1 { rank: CardRankV1; suit: CardSuitV1 }
export type PokerActionV1 = "fold" | "check" | "call" | "bet" | "raise";
export type PokerStreetV1 = "preflop" | "flop" | "turn" | "river";

export interface PokerSeatStateV1 { seat: number; stack: number; bet: number; name?: string }

export interface PokerHandStartPayloadV1 {
  hand_id: string;
  button: number;
  small_blind: number;
  big_blind: number;
  seats: PokerSeatStateV1[];
}
export interface PokerDealPayloadV1 { hand_id: string; seat: number; cards: CardV1[] }
export interface PokerTurnPayloadV1 {
  hand_id: string;
  seat: number;
  actions: PokerActionV1[];
  min?: number;
  max?: number;
  to_call: number;
  pot: number;
}
export interface PokerActionPayloadV1 {
  hand_id: string;
  seat: number;
  action: PokerActionV1;
  amount: number;
  stack: number;
  pot: number;
  street: PokerStreetV1;
}
export interface PokerBoardPayloadV1 { hand_id: string; street: PokerStreetV1; cards: CardV1[] }
export interface PokerChipsPayloadV1 { hand_id: string; from: number | "pot"; to: number | "pot"; amount: number }
export interface PokerShowdownPayloadV1 {
  hand_id: string;
  winners: Array<{ seat: number; amount: number; ranking: string; cards: CardV1[] }>;
  hole: Array<{ seat: number; cards: CardV1[] }>;
}
/** Sent by a /play seat (human) — the dealer applies it if it's that seat's turn. */
export interface PokerIntentPayloadV1 { hand_id?: string; seat: number; action: PokerActionV1; amount?: number }
export interface SeatJoinPayloadV1 { seat: number; name: string; avatar_url?: string; kind: "human" | "bot" }

export function isSetEventType(t: string): t is SetEventTypeV1 {
  return (SET_EVENT_TYPES as readonly string[]).includes(t);
}
