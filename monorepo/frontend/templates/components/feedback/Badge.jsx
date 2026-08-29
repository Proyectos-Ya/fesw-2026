import React from 'react';

const TONES = {
  neutral: { bg: 'var(--warm-100)', fg: 'var(--warm-700)', bd: 'var(--warm-200)' },
  teal:    { bg: 'var(--teal-50)',  fg: 'var(--teal-700)', bd: 'var(--teal-200)' },
  coral:   { bg: 'var(--coral-50)', fg: 'var(--coral-700)', bd: 'var(--coral-200)' },
  success: { bg: 'var(--success-soft)', fg: 'var(--green-600)', bd: 'transparent' },
  warning: { bg: 'var(--warning-soft)', fg: 'var(--amber-600)', bd: 'transparent' },
  danger:  { bg: 'var(--danger-soft)',  fg: 'var(--red-600)',   bd: 'transparent' },
  info:    { bg: 'var(--info-soft)',    fg: 'var(--blue-500)',  bd: 'transparent' },
  solid:   { bg: 'var(--primary)', fg: 'var(--on-primary)', bd: 'transparent' },
};

export function Badge({ children, tone = 'neutral', dot = false, iconLeft = null, style = {} }) {
  const t = TONES[tone] || TONES.neutral;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      fontFamily: 'var(--font-sans)', fontSize: 'var(--text-xs)', fontWeight: 'var(--weight-semibold)',
      lineHeight: 1, letterSpacing: '0.01em', padding: '5px 10px', borderRadius: 'var(--radius-pill)', whiteSpace: 'nowrap',
      background: t.bg, color: t.fg, border: `1px solid ${t.bd}`, ...style,
    }}>
      {dot && <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />}
      {iconLeft}
      {children}
    </span>
  );
}
