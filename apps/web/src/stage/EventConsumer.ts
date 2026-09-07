/**
 * ShowEventConsumer — processes ShowEvents and updates stage state.
 *
 * Handles:
 * - Phase transitions
 * - Character enter/exit
 * - Camera cuts
 * - Performance start/end
 * - Crowd updates
 * - Judge locks/reveals
 * - Audio events
 */

import { useShowStore, ShowEvent, ShowPhase, CameraPreset } from '../store/showStore';

export class EventConsumer {
  private store = useShowStore;
  private ws: WebSocket | null = null;
  private episodeId: string = '';
  private lastSeq: number = 0;

  // ── WebSocket Connection ─────────────────────────────────────────

  async connect(episodeId: string, type: 'stage' | 'audience' = 'stage'): Promise<void> {
    this.episodeId = episodeId;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/live/${episodeId}/ws?type=${type}`;

    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log(`[EventConsumer] Connected as ${type}`);

        // Request snapshot from last known seq
        this.ws?.send(JSON.stringify({
          type: 'ready',
          last_seq: this.lastSeq,
        }));

        resolve();
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          this.handleMessage(data);
        } catch (err) {
          console.error('[EventConsumer] Failed to parse message:', err);
        }
      };

      this.ws.onerror = (err) => {
        console.error('[EventConsumer] WebSocket error:', err);
        reject(err);
      };

      this.ws.onclose = () => {
        console.log('[EventConsumer] Disconnected');
        // Reconnect after delay
        setTimeout(() => this.connect(episodeId, type), 3000);
      };
    });
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  // ── Message Handling ─────────────────────────────────────────────

  private handleMessage(data: any): void {
    const { type } = data;

    // Snapshot
    if (type === 'show.snapshot') {
      this.handleSnapshot(data.data);
      return;
    }

    // Event
    if (data.data?.seq !== undefined) {
      const event = data.data as ShowEvent;
      this.store.getState().applyEvent(event);
      this.lastSeq = Math.max(this.lastSeq, event.seq);
    }

    // Direct type handling
    switch (type) {
      case 'crowd.update':
        this.store.getState().setCrowd(data.data);
        break;
      case 'heartbeat.ack':
        // pong
        break;
    }
  }

  private handleSnapshot(snapshot: any): void {
    const state = this.store.getState();

    // Restore episode state
    if (snapshot.episodeId) {
      state.setEpisode(snapshot.episodeId);
    }
    if (snapshot.phase) {
      state.setPhase(snapshot.phase as ShowPhase);
    }

    // Restore events
    if (snapshot.events) {
      for (const event of snapshot.events) {
        state.applyEvent(event);
      }
    }
  }

  // ── Send Commands ────────────────────────────────────────────────

  sendReaction(type: string, data: Record<string, any> = {}): void {
    this.ws?.send(JSON.stringify({
      type: 'reaction',
      reaction: type,
      ...data,
    }));
  }

  sendHeartbeat(): void {
    this.ws?.send(JSON.stringify({ type: 'heartbeat' }));
  }

  sendCameraCut(camera: CameraPreset): void {
    this.ws?.send(JSON.stringify({
      type: 'camera.cut',
      camera,
      source: 'human_director',
    }));
  }
}
