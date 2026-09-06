/**
 * EpisodeRoom Durable Object — coordinates live show state.
 *
 * One per live episode. Handles:
 * - Current phase
 * - Active appearance
 * - Ordered event sequence
 * - Connected stage/audience WebSockets
 * - Crowd aggregation
 * - Human puppeteer connection
 */

import { DurableObject } from 'cloudflare:workers';

export type EpisodeState = {
  episodeId: string;
  phase: string;
  activeAppearanceId: string | null;
  seq: number;
  startedAt: string | null;
};

export class EpisodeRoom extends DurableObject {
  private state: DurableObjectState;
  private env: any;

  // Connected clients
  private stageClients: Set<WebSocket> = new Set();
  private audienceClients: Set<WebSocket> = new Set();
  private puppeteerClients: Set<WebSocket> = new Set();

  // Live state
  private episodeState: EpisodeState = {
    episodeId: '',
    phase: 'pre_show',
    activeAppearanceId: null,
    seq: 0,
    startedAt: null,
  };

  // Crowd aggregation (in-memory, flushed periodically)
  private crowdWindows: Map<string, { laughs: number; uniqueLaughers: Set<string>; startTime: number }> = new Map();

  constructor(state: DurableObjectState, env: any) {
    super(state, env);
    this.state = state;
    this.env = env;
  }

  /**
   * Handle HTTP requests to the Durable Object.
   */
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === '/ws') {
      return this.handleWebSocketUpgrade(request);
    }

    if (url.pathname === '/state') {
      return Response.json(this.episodeState);
    }

    if (url.pathname === '/command' && request.method === 'POST') {
      return this.handleCommand(request);
    }

    return Response.json({ error: 'Not found' }, { status: 404 });
  }

  /**
   * Handle WebSocket connections.
   */
  private handleWebSocketUpgrade(request: Request): Response {
    const pair = new WebSocketPair();
    const [client, server] = [pair[0], pair[1]];

    this.ctx.acceptWebSocket(server);

    // Determine client type from query params
    const url = new URL(request.url);
    const clientType = url.searchParams.get('type') || 'audience';

    if (clientType === 'stage') {
      this.stageClients.add(server);
    } else if (clientType === 'puppeteer') {
      this.puppeteerClients.add(server);
    } else {
      this.audienceClients.add(server);
    }

    // Send current state snapshot
    server.send(JSON.stringify({
      type: 'show.snapshot',
      data: this.episodeState,
    }));

    return new Response(null, { status: 101, webSocket: client });
  }

  /**
   * Handle WebSocket messages.
   */
  async webSocketMessage(ws: WebSocket, message: string | ArrayBuffer) {
    try {
      const data = JSON.parse(message as string);
      const { type } = data;

      // Audience messages
      if (type === 'reaction' && this.audienceClients.has(ws)) {
        this.handleReaction(data, ws);
      }

      // Stage messages
      if (type === 'ready' && this.stageClients.has(ws)) {
        // Send full state
        ws.send(JSON.stringify({
          type: 'show.snapshot',
          data: this.episodeState,
        }));
      }

      if (type === 'ack' && this.stageClients.has(ws)) {
        // Client acknowledged an event
      }

      // Puppeteer messages
      if (type === 'dialogue' && this.puppeteerClients.has(ws)) {
        this.handlePuppeteerDialogue(data);
      }

      // Heartbeat
      if (type === 'heartbeat') {
        ws.send(JSON.stringify({ type: 'heartbeat.ack' }));
      }
    } catch (err) {
      console.error('WebSocket message error:', err);
    }
  }

  /**
   * Handle WebSocket close.
   */
  async webSocketClose(ws: WebSocket) {
    this.stageClients.delete(ws);
    this.audienceClients.delete(ws);
    this.puppeteerClients.delete(ws);
  }

  /**
   * Handle a command from the admin/API.
   */
  private async handleCommand(request: Request): Promise<Response> {
    const body = await request.json() as any;
    const { commandId, type, payload } = body;

    // Idempotency check
    if (commandId) {
      const existing = await this.state.storage.get(`cmd:${commandId}`);
      if (existing) {
        return Response.json({ status: 'already_executed', eventId: existing });
      }
    }

    // Validate and execute command
    const event = await this.executeCommand(type, payload);

    // Store idempotency
    if (commandId && event) {
      await this.state.storage.put(`cmd:${commandId}`, event.seq);
    }

    return Response.json({ status: 'ok', event });
  }

  /**
   * Execute a show command.
   */
  private async executeCommand(type: string, payload: any): Promise<any> {
    // Allocate sequence number
    this.episodeState.seq++;
    const seq = this.episodeState.seq;

    const event = {
      seq,
      type,
      actor: payload.actor || 'system',
      payload,
      createdAt: new Date().toISOString(),
    };

    // Persist to storage
    await this.state.storage.put(`event:${seq}`, event);

    // Update state based on command
    switch (type) {
      case 'show.start':
        this.episodeState.phase = 'intro';
        this.episodeState.startedAt = new Date().toISOString();
        break;
      case 'show.phase':
        this.episodeState.phase = payload.phase;
        break;
      case 'character.enter':
        this.episodeState.activeAppearanceId = payload.appearanceId;
        break;
      case 'character.exit':
        this.episodeState.activeAppearanceId = null;
        break;
      case 'show.end':
        this.episodeState.phase = 'ended';
        break;
    }

    // Persist updated state
    await this.state.storage.put('state', this.episodeState);

    // Broadcast to all clients
    this.broadcast(JSON.stringify({
      type,
      data: event,
    }));

    return event;
  }

  /**
   * Handle audience reaction.
   */
  private handleReaction(data: any, ws: WebSocket) {
    const { reaction, appearanceId, clientSeq } = data;

    // Add server timestamp
    const serverEvent = {
      type: 'reaction',
      reaction,
      appearanceId: appearanceId || this.episodeState.activeAppearanceId,
      serverTimestamp: Date.now(),
      clientSeq,
    };

    // Aggregate in memory
    const windowKey = this.episodeState.activeAppearanceId || 'none';
    if (!this.crowdWindows.has(windowKey)) {
      this.crowdWindows.set(windowKey, {
        laughs: 0,
        uniqueLaughers: new Set(),
        startTime: Date.now(),
      });
    }
    const window = this.crowdWindows.get(windowKey)!;
    if (reaction === 'laugh') {
      window.laughs++;
      // Simple client dedup (in production, use session ID)
      window.uniqueLaughers.add(clientSeq);
    }

    // Broadcast aggregate to audience
    this.broadcastToAudience(JSON.stringify({
      type: 'crowd.update',
      data: {
        laughs: window.laughs,
        uniqueLaughers: window.uniqueLaughers.size,
      },
    }));
  }

  /**
   * Handle puppeteer dialogue.
   */
  private handlePuppeteerDialogue(data: any) {
    const { text, appearanceId } = data;

    this.episodeState.seq++;
    const event = {
      seq: this.episodeState.seq,
      type: 'stage.speak',
      actor: `contestant_${appearanceId}`,
      payload: { text, appearanceId },
      createdAt: new Date().toISOString(),
    };

    // Broadcast to stage
    this.broadcastToStage(JSON.stringify({
      type: 'stage.speak',
      data: event,
    }));
  }

  /**
   * Broadcast to all connected clients.
   */
  private broadcast(message: string) {
    for (const ws of this.stageClients) {
      try { ws.send(message); } catch {}
    }
    for (const ws of this.audienceClients) {
      try { ws.send(message); } catch {}
    }
  }

  /**
   * Broadcast to stage clients only.
   */
  private broadcastToStage(message: string) {
    for (const ws of this.stageClients) {
      try { ws.send(message); } catch {}
    }
  }

  /**
   * Broadcast to audience clients only.
   */
  private broadcastToAudience(message: string) {
    for (const ws of this.audienceClients) {
      try { ws.send(message); } catch {}
    }
  }

  /**
   * Alarm handler for periodic crowd aggregation persistence.
   */
  async alarm() {
    // Persist crowd windows to D1
    // Reset in-memory windows
    this.crowdWindows.clear();

    // Set next alarm (every 5 seconds)
    await this.ctx.storage.setAlarm(Date.now() + 5000);
  }
}
