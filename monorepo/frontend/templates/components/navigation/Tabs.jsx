import React from 'react';

export function Tabs({ tabs = [], value, onChange, style = {} }) {
  const items = tabs.map((t) => (typeof t === 'string' ? { value: t, label: t } : t));
  const active = value ?? items[0]?.value;
  return (
    <div role="tablist" style={{
      display: 'flex', gap: 4, borderBottom: '1px solid var(--border-subtle)',
      fontFamily: 'var(--font-sans)', ...style,
    }}>
      {items.map((t) => {
        const isActive = t.value === active;
        return (
          <button
            key={t.value} role="tab" aria-selected={isActive} onClick={() => onChange && onChange(t.value)}
            style={{
              position: 'relative', border: 'none', background: 'transparent', cursor: 'pointer',
              padding: '10px 14px 12px', marginBottom: -1,
              fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-semibold)',
              color: isActive ? 'var(--text-strong)' : 'var(--text-muted)',
              display: 'inline-flex', alignItems: 'center', gap: 7,
              transition: 'color var(--dur-fast) var(--ease-standard)',
            }}
          >
            {t.icon}
            {t.label}
            {t.count != null && (
              <span style={{
                fontFamily: 'var(--font-mono)', fontSize: 11, padding: '1px 7px', borderRadius: 'var(--radius-pill)',
                background: isActive ? 'var(--primary-soft)' : 'var(--warm-100)',
                color: isActive ? 'var(--primary-active)' : 'var(--text-muted)',
              }}>{t.count}</span>
            )}
            <span style={{
              position: 'absolute', left: 8, right: 8, bottom: 0, height: 2.5, borderRadius: '3px 3px 0 0',
              background: isActive ? 'var(--primary)' : 'transparent',
              transition: 'background var(--dur-fast) var(--ease-standard)',
            }} />
          </button>
        );
      })}
    </div>
  );
}
