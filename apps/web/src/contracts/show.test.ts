/**
 * Shared contract tests — golden fixtures validate both the Zod schemas
 * and (via backend/contracts.py + tests/unit/test_contracts.py) the
 * Pydantic mirror against the SAME JSON.
 */
import { describe, expect, it } from 'vitest';
import {
  ShowEventV1,
  ReactionRawV1,
  SnapshotV1,
  CrowdUpdateV1,
  CameraCutPayloadV1,
  PerformancePreloadPayloadV1,
  DeliveryV1,
  AvatarV1,
  BundleV1,
  JudgeReactPayloadV1,
  PanelSeatPayloadV1,
  CharacterModesV1,
  EllaSenseV1,
  EllaActionV1,
  CAMERA_NAMES,
} from './show';

describe('wire contracts', () => {
  it('accepts a canonical show event', () => {
    const parsed = ShowEventV1.safeParse({
      seq: 943,
      type: 'camera.cut',
      actor: 'control',
      payload: { camera: 'COMIC_CLOSE' },
      created_at: '2026-09-07T19:00:00.000Z',
    });
    expect(parsed.success).toBe(true);
  });

  it('rejects camelCase timestamps (wire is snake_case)', () => {
    const parsed = ShowEventV1.safeParse({
      seq: 1,
      type: 'show.start',
      actor: 'system',
      payload: {},
      createdAt: '2026-09-07T19:00:00.000Z',
    });
    expect(parsed.success).toBe(false);
  });

  it('accepts a raw ML reaction', () => {
    const parsed = ReactionRawV1.safeParse({
      seq: 101,
      event_id: '123e4567-e89b-12d3-a456-426614174000',
      episode_id: 'ep1',
      performance_id: 'perf1',
      session_id: 'sess1',
      client_seq: 81,
      type: 'reaction',
      reaction: 'laugh',
      set_time_ms: 18322,
      server_received_at: '2026-09-07T19:00:18.322Z',
      source: 'freaktown_web',
    });
    expect(parsed.success).toBe(true);
  });

  it('rejects unknown reactions and bad client_seq', () => {
    expect(
      ReactionRawV1.safeParse({
        seq: 1,
        event_id: '123e4567-e89b-12d3-a456-426614174000',
        episode_id: 'e', performance_id: 'p', session_id: 's',
        client_seq: 0, type: 'reaction', reaction: 'laugh',
        set_time_ms: 0, server_received_at: '2026-09-07T19:00:00.000Z',
        source: 'web',
      }).success
    ).toBe(false);
    expect(
      ReactionRawV1.safeParse({
        seq: 1,
        event_id: '123e4567-e89b-12d3-a456-426614174000',
        episode_id: 'e', performance_id: 'p', session_id: 's',
        client_seq: 1, type: 'reaction', reaction: 'scream',
        set_time_ms: 0, server_received_at: '2026-09-07T19:00:00.000Z',
        source: 'web',
      }).success
    ).toBe(false);
  });

  it('accepts snapshots and crowd updates', () => {
    expect(SnapshotV1.safeParse({
      episode_id: 'ep1', phase: 'set_active', active_appearance_id: 'a1',
      seq: 42, is_paused: false,
    }).success).toBe(true);
    expect(CrowdUpdateV1.safeParse({
      laugh_events: 10, claps: 2, boos: 0,
      crickets: 0, groans: 1, unique_laughers: 4,
    }).success).toBe(true);
  });

  it('rejects unknown camera presets', () => {
    expect(CameraCutPayloadV1.safeParse({
      camera: 'CLOSEUP', source: 'human_director',
    }).success).toBe(false);
    expect(CameraCutPayloadV1.safeParse({
      camera: 'COMIC_CLOSE', performance_id: 'p1',
      set_time_ms: 18291, source: 'human_director',
    }).success).toBe(true);
  });

  it('accepts preload payloads', () => {
    expect(PerformancePreloadPayloadV1.safeParse({
      performance_id: 'perf1',
      avatar_url: 'https://cdn/x.glb',
      audio_url: 'https://cdn/y.wav',
      plan: {},
    }).success).toBe(true);
    expect(PerformancePreloadPayloadV1.safeParse({
      performance_id: 'perf1', audio_url: 'https://cdn/y.wav', plan: {},
    }).success).toBe(false);
  });

  it('accepts judge cameras, reactions, seats and modes', () => {
    expect(CAMERA_NAMES).toContain('CHATGPT_CLOSE');
    expect(CAMERA_NAMES).toContain('STREAM_CLOSE');
    expect(CameraCutPayloadV1.safeParse({
      camera: 'STREAM_CLOSE', source: 'human_director',
    }).success).toBe(true);
    expect(JudgeReactPayloadV1.safeParse({
      judge: 'ella', reaction: 'iris_narrow',
    }).success).toBe(true);
    expect(JudgeReactPayloadV1.safeParse({
      judge: 'ella', reaction: 'fireworks',
    }).success).toBe(false);
    expect(PanelSeatPayloadV1.safeParse({
      seat: 'stream-left', character_id: 'c1', reason: 'previous-winner',
    }).success).toBe(true);
    expect(PanelSeatPayloadV1.safeParse({
      seat: 'middle', character_id: 'c1',
    }).success).toBe(false);
    expect(CharacterModesV1.safeParse({
      performer: { stance: 'stage' },
      judge: { seat: 'stream-left', authority: 'commentary' },
    }).success).toBe(true);
    expect(CharacterModesV1.safeParse({
      judge: { seat: 'middle' },
    }).success).toBe(false);
  });

  it('accepts ella sense and action events', () => {
    expect(EllaSenseV1.safeParse({
      episode_id: 'ep1', phase: 'set_active', active_appearance_id: 'perf1',
      seq: 200, is_paused: false, set_time_ms: null,
      crowd: {
        laugh_events: 93, claps: 10, boos: 0,
        crickets: 0, groans: 4, unique_laughers: 40,
      },
      pot_cents: 100,
      updated_at: '2026-09-08T20:00:18.000Z',
    }).success).toBe(true);
    expect(EllaActionV1.safeParse({
      set_time_ms: 42188, trigger: 'audience_laugh_spike',
      action: 'look_at_chatgpt', latency_ms: 37, source: 'reflex-v1',
    }).success).toBe(true);
    expect(EllaActionV1.safeParse({
      trigger: 'x', action: 'y', latency_ms: 0, source: 'vibes-v9',
    }).success).toBe(false);
  });

  it('accepts delivery/avatar/bundle documents', () => {
    const delivery = {
      version: 'freaktown.delivery.v1',
      voice: { provider: 'edge-tts', voice_id: 'v' },
      beats: [{ id: 'b1', type: 'punchline', text: 'Hi.' }],
    };
    expect(DeliveryV1.safeParse(delivery).success).toBe(true);
    const avatar = {
      version: 'freaktown.avatar.v1', format: 'vrm', asset: 'avatar.vrm',
      capabilities: { humanoid: false, visemes: ['aa'] },
    };
    expect(AvatarV1.safeParse(avatar).success).toBe(true);
    expect(AvatarV1.safeParse({ ...avatar, format: 'glb' }).success).toBe(false);
    expect(BundleV1.safeParse({
      character: { name: 'Martin Lamp' }, delivery, avatar,
    }).success).toBe(true);
  });
});
