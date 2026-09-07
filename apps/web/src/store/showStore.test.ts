/**
 * showStore unit tests — event idempotency and judge-reveal gating.
 */
import { describe, expect, it, beforeEach } from 'vitest';
import { useShowStore } from './showStore';

function reset(): void {
  useShowStore.setState({
    events: [],
    lastSeq: 0,
    phase: 'pre_show',
    isPaused: false,
    scoresRevealed: false,
    judgeScores: [],
  });
}

function ev(seq: number, type: string, payload: Record<string, unknown> = {}) {
  return {
    seq, type, actor: 'system', payload,
    created_at: new Date().toISOString(),
  };
}

beforeEach(reset);

describe('showStore.applyEvent', () => {
  it('ignores duplicate and out-of-order seqs', () => {
    const s = useShowStore.getState();
    s.applyEvent(ev(1, 'show.start'));
    s.applyEvent(ev(2, 'phase.change', { phase: 'intro' }));
    s.applyEvent(ev(2, 'phase.change', { phase: 'intro' })); // dup
    s.applyEvent(ev(1, 'show.start')); // stale
    const st = useShowStore.getState();
    expect(st.events).toHaveLength(2);
    expect(st.lastSeq).toBe(2);
  });

  it('keeps scores hidden until judge.reveal', () => {
    const s = useShowStore.getState();
    s.setJudgeScores([{ name: 'Ella', score: 8.1, feedback: 'x' }]);
    expect(useShowStore.getState().scoresRevealed).toBe(false);
    s.applyEvent(ev(3, 'judge.ella.locked', { score: 8.1 }));
    expect(useShowStore.getState().scoresRevealed).toBe(false);
    s.applyEvent(ev(4, 'judge.reveal', {}));
    expect(useShowStore.getState().scoresRevealed).toBe(true);
  });

  it('applies camera cuts and crowd aggregates', () => {
    const s = useShowStore.getState();
    s.applyEvent(ev(1, 'camera.cut', { camera: 'COMIC_CLOSE' }));
    expect(useShowStore.getState().currentCamera).toBe('COMIC_CLOSE');
    s.applyEvent(ev(2, 'crowd.aggregate', { laugh_events: 10, unique_laughers: 4 }));
    const crowd = useShowStore.getState().crowd;
    expect(crowd.laugh_events).toBe(10);
    expect(crowd.unique_laughers).toBe(4);
  });
});
