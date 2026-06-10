import React from 'react';

export function Switch({ checked = false, onChange, label, disabled = false, id, style = {} }) {
  const autoId = React.useId();
  const fieldId = id || autoId;
  return (
    <label htmlFor={fieldId} style={{
      display: 'inline-flex', alignItems: 'center', gap: 10, cursor: disabled ? 'not-allowed' : 'pointer',
      fontFamily: 'var(--font-sans)', fontSize: 'var(--text-base)', color: 'var(--text-body)',
      opacity: disabled ? 0.5 : 1, ...style,
    }}>
      <input id={fieldId} type="checkbox" checked={checked} disabled={disabled}
        onChange={(e) => onChange && onChange(e.target.checked, e)}
        style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }} />
      <span style={{
        width: 40, height: 24, borderRadius: 'var(--radius-pill)', flex: 'none', position: 'relative',
        background: checked ? 'var(--primary)' : 'var(--warm-300)',
        transition: 'background var(--dur-base) var(--ease-standard)',
      }}>
        <span style={{
          position: 'absolute', top: 3, left: checked ? 19 : 3, width: 18, height: 18, borderRadius: '50%',
          background: 'var(--white)', boxShadow: 'var(--shadow-sm)',
          transition: 'left var(--dur-base) var(--ease-out)',
        }} />
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
