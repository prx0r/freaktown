/**
 * LivePage — audience view for the live show.
 *
 * This is what audience members see in their browser.
 * Same stage events as OBS, but with interactive elements.
 *
 * URL: /live/:episodeId
 */

import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useShowStore } from '../store/showStore';
import { payForAction } from '../x402/pay';

export function LivePage() {
  const { episodeId } = useParams<{ episodeId: string }>();

  const phase = useShowStore((s) => s.phase);
  const currentTimeMs = useShowStore((s) => s.currentTimeMs);
  const crowd = useShowStore((s) => s.crowd);
  const scoresRevealed = useShowStore((s) => s.scoresRevealed);
  const judgeScores = useShowStore((s) => s.judgeScores);

  const [wsConnected, setWsConnected] = useState(false);
  const [payNote, setPayNote] = useState<string | null>(null);
  const [paying, setPaying] = useState(false);

  // Format time as MM:SS
  const formatTime = (ms: number): string => {
    const totalSeconds = Math.floor(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const handleReaction = (type: string) => {
    // Send reaction via WebSocket
    // This will be connected to the EventConsumer
    console.log(`Reaction: ${type}`);
  };

  const handlePaid = async (action: 'pot' | 'message' | 'hype' | 'tip') => {
    if (paying || !episodeId) return;
    setPaying(true);
    setPayNote(null);
    const message =
      action === 'message' ? window.prompt('Message to flash on screen (140 chars):', '') ?? '' : '';
    if (action === 'message' && !message) {
      setPaying(false);
      return;
    }
    const result = await payForAction({ action, showId: episodeId, message });
    setPaying(false);
    // The settled payment is already a show event by the time the modal
    // resolves — EventConsumer picks it up over the live socket.
    setPayNote(result.ok ? 'Payment settled — on screen!' : `Payment failed: ${result.error}`);
  };

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      background: '#0a0a0f',
      color: '#e0e0e0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Stage area (would be the Three.js renderer in production) */}
      <div style={{
        flex: 1,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0f0f14',
        position: 'relative',
      }}>
        <div style={{
          fontSize: 24,
          opacity: 0.3,
        }}>
          STAGE VIEW
        </div>

        {/* Phase indicator */}
        <div style={{
          position: 'absolute',
          top: 16,
          left: 16,
          fontSize: 12,
          fontFamily: 'monospace',
          opacity: 0.5,
        }}>
          {phase.replace(/_/g, ' ').toUpperCase()}
        </div>

        {/* Timer */}
        <div style={{
          position: 'absolute',
          top: 16,
          right: 16,
          fontSize: 18,
          fontFamily: 'monospace',
          fontWeight: 'bold',
        }}>
          {formatTime(currentTimeMs)}
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        padding: '16px 20px',
        borderTop: '1px solid #222',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Reaction buttons */}
        <div style={{ display: 'flex', gap: 12 }}>
          <ReactionButton
            emoji="😂"
            label="HAHA"
            count={crowd.laugh_events}
            onClick={() => handleReaction('laugh')}
          />
          <ReactionButton
            emoji="👏"
            label="CLAP"
            count={crowd.claps}
            onClick={() => handleReaction('clap')}
          />
          <ReactionButton
            emoji="🦗"
            label="CRICKETS"
            count={0}
            onClick={() => handleReaction('crickets')}
          />
        </div>

        {/* Paid actions (x402) */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <PaidButton emoji="🏺" label="POT $1+" onClick={() => handlePaid('pot')} disabled={paying} />
          <PaidButton emoji="📣" label="MSG $2" onClick={() => handlePaid('message')} disabled={paying} />
          <PaidButton emoji="🔥" label="HYPE $5" onClick={() => handlePaid('hype')} disabled={paying} />
          <PaidButton emoji="💸" label="TIP $1+" onClick={() => handlePaid('tip')} disabled={paying} />
        </div>

        {payNote && (
          <div style={{ fontSize: 12, opacity: 0.7 }}>
            {payNote}
          </div>
        )}

        {/* Crowd stats */}
        <div style={{
          fontSize: 12,
          opacity: 0.5,
          display: 'flex',
          gap: 16,
        }}>
          <span>{crowd.active_viewers} watching</span>
          <span>{crowd.unique_laughers} laughing</span>
        </div>
      </div>

      {/* Score reveal overlay */}
      {scoresRevealed && (
        <div style={{
          position: 'absolute',
          bottom: 80,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          gap: 16,
          padding: 16,
          background: 'rgba(0,0,0,0.9)',
          borderRadius: 8,
          border: '1px solid #333',
        }}>
          {judgeScores.map((s) => (
            <div
              key={s.name}
              style={{
                padding: '12px 16px',
                background: '#1a1a24',
                borderRadius: 6,
                textAlign: 'center',
                minWidth: 100,
              }}
            >
              <div style={{ fontSize: 11, opacity: 0.5, marginBottom: 4 }}>{s.name}</div>
              <div style={{
                fontSize: 28,
                fontWeight: 'bold',
                color: s.score >= 7 ? '#4a9' : s.score >= 5 ? '#aa4' : '#a44',
              }}>
                {s.score.toFixed(1)}
              </div>
              {s.verdict && (
                <div style={{
                  fontSize: 10,
                  marginTop: 4,
                  padding: '2px 6px',
                  borderRadius: 3,
                  background: s.verdict === 'KEEP' ? '#1a3a1a' : '#3a1a1a',
                  color: s.verdict === 'KEEP' ? '#4a9' : '#a44',
                }}>
                  {s.verdict}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Reaction Button ──────────────────────────────────────────────

function ReactionButton({
  emoji,
  label,
  count,
  onClick,
}: {
  emoji: string;
  label: string;
  count: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        padding: '12px 16px',
        border: '1px solid #333',
        borderRadius: 8,
        background: '#1a1a24',
        color: '#e0e0e0',
        cursor: 'pointer',
        transition: 'all 0.15s',
        minWidth: 70,
      }}
    >
      <span style={{ fontSize: 24 }}>{emoji}</span>
      <span style={{ fontSize: 10, opacity: 0.7 }}>{label}</span>
      {count > 0 && (
        <span style={{ fontSize: 11, fontWeight: 'bold' }}>{count}</span>
      )}
    </button>
  );
}

// ── Paid Button (x402) ─────────────────────────────────────────────

function PaidButton({
  emoji,
  label,
  onClick,
  disabled,
}: {
  emoji: string;
  label: string;
  onClick: () => void;
  disabled: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 4,
        padding: '12px 16px',
        border: '1px solid #6b5320',
        borderRadius: 8,
        background: '#241d0e',
        color: '#e0e0e0',
        cursor: disabled ? 'wait' : 'pointer',
        transition: 'all 0.15s',
        minWidth: 70,
        opacity: disabled ? 0.6 : 1,
      }}
    >
      <span style={{ fontSize: 24 }}>{emoji}</span>
      <span style={{ fontSize: 10, opacity: 0.7 }}>{label}</span>
    </button>
  );
}
