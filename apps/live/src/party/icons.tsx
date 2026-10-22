/**
 * Inline SVG icons for the party pages. Emoji glyphs depend on the device having
 * a colour-emoji font (headless Chromium / many Linux boxes render tofu boxes),
 * so every party UI icon is drawn here instead. currentColor, 1em by default.
 */
import React from 'react';

type P = { size?: number | string; className?: string; title?: string; style?: React.CSSProperties };
const S = ({ size = '1em', className, title, style, children, vb = '0 0 24 24' }: P & { children: React.ReactNode; vb?: string }) => (
  <svg viewBox={vb} width={size} height={size} className={`ic ${className ?? ''}`} style={{ verticalAlign: '-0.14em', flex: 'none', ...style }} aria-hidden={title ? undefined : true} role={title ? 'img' : undefined}>
    {title && <title>{title}</title>}
    {children}
  </svg>
);

export const IconSmile = (p: P) => (
  <S {...p}><circle cx="12" cy="12" r="10" fill="#FFD25A" /><circle cx="8.6" cy="9.6" r="1.4" fill="#3a2a10" /><circle cx="15.4" cy="9.6" r="1.4" fill="#3a2a10" /><path d="M6.8 13.2c1.2 3.2 3 4.6 5.2 4.6s4-1.4 5.2-4.6z" fill="#3a2a10" /><path d="M8.6 14.4c1 1.5 2.1 2.1 3.4 2.1s2.4-.6 3.4-2.1z" fill="#fff" /></S>
);
export const IconSkull = (p: P) => (
  <S {...p}><path d="M12 2.5c-4.9 0-8.5 3.5-8.5 8 0 2.6 1.2 4.5 3 5.6V19a1.5 1.5 0 0 0 1.5 1.5h1V18h1.3v2.5h3.4V18H15v2.5h1a1.5 1.5 0 0 0 1.5-1.5v-2.9c1.8-1.1 3-3 3-5.6 0-4.5-3.6-8-8.5-8z" fill="#f4f1ea" /><circle cx="8.6" cy="11" r="2.1" fill="#1b1a22" /><circle cx="15.4" cy="11" r="2.1" fill="#1b1a22" /><path d="M12 13.4l-1.3 2.2h2.6z" fill="#1b1a22" /></S>
);
export const IconMic = (p: P) => (
  <S {...p}><rect x="9" y="2.5" width="6" height="11" rx="3" fill="currentColor" /><path d="M6 11a6 6 0 0 0 12 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /><path d="M12 17v4M8.5 21h7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></S>
);
export const IconLock = (p: P) => (
  <S {...p}><rect x="5" y="10.5" width="14" height="10" rx="2" fill="currentColor" /><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" fill="none" stroke="currentColor" strokeWidth="2.2" /></S>
);
export const IconBulb = (p: P) => (
  <S {...p}><path d="M12 2.5a6.5 6.5 0 0 0-3.8 11.8c.6.5 1 1.2 1 2V17h5.6v-.7c0-.8.4-1.5 1-2A6.5 6.5 0 0 0 12 2.5z" fill="currentColor" /><path d="M9.5 19h5M10.3 21.3h3.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></S>
);
export const IconHeart = (p: P) => (
  <S {...p}><path d="M12 20.5s-7.5-4.6-9.2-9.3C1.6 7.8 3.9 4.5 7.3 4.5c2 0 3.6 1.1 4.7 2.8 1.1-1.7 2.7-2.8 4.7-2.8 3.4 0 5.7 3.3 4.5 6.7-1.7 4.7-9.2 9.3-9.2 9.3z" fill="currentColor" /></S>
);
export const IconTrophy = (p: P) => (
  <S {...p}><path d="M7 3h10v5a5 5 0 0 1-10 0z" fill="currentColor" /><path d="M7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3" fill="none" stroke="currentColor" strokeWidth="1.8" /><path d="M10.5 13h3v4h-3zM7.5 18h9v3h-9z" fill="currentColor" /></S>
);
