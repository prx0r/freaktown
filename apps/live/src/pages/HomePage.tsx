import React from 'react';
import { Link } from 'react-router-dom';

export function HomePage() {
  const ep = 'demo';
  const link: React.CSSProperties = { color: '#9fd8ff', display: 'block', margin: '8px 0', fontSize: 18 };
  return (
    <div style={{ minHeight: '100vh', background: '#0c0a12', color: '#eee', fontFamily: 'Inter, system-ui, sans-serif', padding: 32 }}>
      <div style={{ fontSize: 12, letterSpacing: 3, color: '#ff7ac8' }}>FREAK TOWN · LIVE STAGE</div>
      <h1 style={{ marginTop: 4 }}>Live stage</h1>
      <p style={{ opacity: 0.75, maxWidth: 560 }}>
        Open the stage (program feed) and the control console side by side. Local mode runs entirely in
        this browser; add <code>?transport=room</code> to drive the Cloudflare EpisodeRoom instead.
      </p>
      <Link style={link} to={`/control/${ep}`}>Control → /control/{ep}</Link>
      <Link style={link} to={`/stage/${ep}?debug=1`}>Stage → /stage/{ep}</Link>
      <Link style={link} to={`/live/${ep}`}>Audience → /live/{ep}</Link>
    </div>
  );
}
