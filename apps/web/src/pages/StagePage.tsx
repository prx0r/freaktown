/**
 * StagePage — the production stage view.
 *
 * This is what OBS Browser Source captures.
 * Full-screen Three.js renderer with VRM avatar.
 *
 * URL: /stage/:episodeId
 */

import React, { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { StageRuntime } from '../stage/StageRuntime';
import { useShowStore, CAMERA_PRESETS, CameraPreset } from '../store/showStore';

export function StagePage({ episodeId: propEpisodeId }: { episodeId?: string }) {
  const { episodeId: urlEpisodeId } = useParams<{ episodeId: string }>();
  const episodeId = propEpisodeId || urlEpisodeId || 'demo';

  const containerRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<StageRuntime | null>(null);
  const [isLoaded, setIsLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const phase = useShowStore((s) => s.phase);
  const currentTimeMs = useShowStore((s) => s.currentTimeMs);
  const currentCamera = useShowStore((s) => s.currentCamera);

  useEffect(() => {
    if (!containerRef.current) return;

    const runtime = new StageRuntime({
      mode: 'live',
      container: containerRef.current,
      background: '#0a0a1a',
    });

    runtimeRef.current = runtime;

    // Connect to episode
    runtime.connect(episodeId).catch(console.error);

    setIsLoaded(true);

    return () => {
      runtime.dispose();
      runtimeRef.current = null;
    };
  }, [episodeId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      // Camera cuts
      const runtime = runtimeRef.current;
      if (runtime) {
        runtime.cutCamera(e.key as unknown as CameraPreset);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Format time as MM:SS
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      position: 'relative',
      overflow: 'hidden',
      background: '#000',
    }}>
      {/* Three.js container */}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          height: '100%',
          position: 'absolute',
          top: 0,
          left: 0,
        }}
      />

      {/* Overlay: Phase indicator */}
      <div style={{
        position: 'absolute',
        top: 20,
        left: 20,
        color: '#fff',
        fontSize: 14,
        fontFamily: 'monospace',
        background: 'rgba(0,0,0,0.6)',
        padding: '8px 12px',
        borderRadius: 4,
        zIndex: 10,
      }}>
        <div style={{ opacity: 0.7, marginBottom: 4 }}>PHASE</div>
        <div style={{ fontSize: 18, fontWeight: 'bold' }}>{phase.toUpperCase()}</div>
      </div>

      {/* Overlay: Timer */}
      <div style={{
        position: 'absolute',
        top: 20,
        right: 20,
        color: '#fff',
        fontSize: 14,
        fontFamily: 'monospace',
        background: 'rgba(0,0,0,0.6)',
        padding: '8px 12px',
        borderRadius: 4,
        zIndex: 10,
      }}>
        <div style={{ opacity: 0.7, marginBottom: 4 }}>TIME</div>
        <div style={{ fontSize: 24, fontWeight: 'bold' }}>{formatTime(currentTimeMs)}</div>
      </div>

      {/* Overlay: Camera indicator */}
      <div style={{
        position: 'absolute',
        bottom: 20,
        right: 20,
        color: '#fff',
        fontSize: 12,
        fontFamily: 'monospace',
        background: 'rgba(0,0,0,0.6)',
        padding: '6px 10px',
        borderRadius: 4,
        zIndex: 10,
      }}>
        CAM: {currentCamera}
      </div>

      {/* Loading state */}
      {!isLoaded && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#fff',
          fontSize: 18,
          zIndex: 20,
        }}>
          Loading stage...
        </div>
      )}

      {/* Error state */}
      {error && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#ff4444',
          fontSize: 16,
          zIndex: 20,
        }}>
          {error}
        </div>
      )}
    </div>
  );
}
