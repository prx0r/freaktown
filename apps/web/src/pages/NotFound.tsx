import React from 'react';
import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#0a0a0f',
      color: '#e0e0e0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    }}>
      <h1 style={{ fontSize: 64, fontWeight: 'bold', margin: 0, opacity: 0.3 }}>404</h1>
      <p style={{ fontSize: 18, opacity: 0.5, marginTop: 8 }}>Not found</p>
      <Link
        to="/"
        style={{
          marginTop: 24,
          padding: '10px 20px',
          border: '1px solid #444',
          borderRadius: 6,
          color: '#e0e0e0',
          textDecoration: 'none',
        }}
      >
        Back to home
      </Link>
    </div>
  );
}
