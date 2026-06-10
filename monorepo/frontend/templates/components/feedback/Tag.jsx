import React from 'react';

export function Tag({ children, active = false, onRemove, onClick, iconLeft = null, style = {} }) {
  const [hover, setHover] = React.useState(false);
  const clickable = onClick || onRemove;
  return (
    <span
      onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 6,
        fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)',
        padding: '6px 12px', borderRadius: 'var(--radius-pill)', whiteSpace: 'nowrap',
        background: active ? 'var(--primary-soft)' : (hover && clickable ? 'var(--warm-100)' : 'var(--surface-card)'),
        color: active ? 'var(--primary-active)' : 'var(--text-body)',
        border: `1px solid ${active ? 'var(--primary-border)' : 'var(--border-default)'}`,
        cursor: clickable ? 'pointer' : 'default',
        transition: 'background var(--dur-fast) var(--ease-standard)', ...style,
      }}
    >
      {iconLeft}
      {children}
      {onRemove && (
        <button type="button" aria-label="Quitar" onClick={(e) => { e.stopPropagation(); onRemove(e); }}
          style={{ display: 'inline-flex', border: 'none', background: 'transparent', padding: 0, marginRight: -2, cursor: 'pointer', color: 'inherit', opacity: 0.7 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round"><path d="M18 6 6 18M6 6l12 12" /></svg>
        </button>
      )}
    </span>
  );
}
