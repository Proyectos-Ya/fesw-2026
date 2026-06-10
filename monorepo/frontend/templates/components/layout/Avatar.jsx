import React from 'react';

const SIZES = { xs: 24, sm: 32, md: 40, lg: 56 };
const PALETTE = ['var(--teal-500)', 'var(--coral-500)', 'var(--teal-700)', 'var(--amber-500)', 'var(--blue-500)', 'var(--green-500)'];

function initials(name = '') {
  return name.trim().split(/\s+/).slice(0, 2).map((w) => w[0] || '').join('').toUpperCase();
}

export function Avatar({ name = '', src, size = 'md', shape = 'circle', style = {} }) {
  const dim = SIZES[size] || SIZES.md;
  const radius = shape === 'square' ? 'var(--radius-md)' : '50%';
  const idx = name ? name.charCodeAt(0) % PALETTE.length : 0;

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      width: dim, height: dim, borderRadius: radius, flex: 'none', overflow: 'hidden',
      background: src ? 'var(--warm-200)' : PALETTE[idx], color: 'var(--white)',
      fontFamily: 'var(--font-sans)', fontWeight: 'var(--weight-semibold)',
      fontSize: dim * 0.4, letterSpacing: '0.01em', userSelect: 'none', ...style,
    }}>
      {src
        ? <img src={src} alt={name} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
        : initials(name)}
    </span>
  );
}
