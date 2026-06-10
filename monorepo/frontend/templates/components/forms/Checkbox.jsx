import React from 'react';

export function Checkbox({ checked = false, onChange, label, disabled = false, id, style = {} }) {
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
        width: 20, height: 20, borderRadius: 'var(--radius-xs)', flex: 'none',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        background: checked ? 'var(--primary)' : 'var(--surface-card)',
        border: `1.5px solid ${checked ? 'var(--primary)' : 'var(--border-strong)'}`,
        transition: 'background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard)',
      }}>
        {checked && (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--on-primary)" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 6 9 17l-5-5" />
          </svg>
        )}
      </span>
      {label && <span>{label}</span>}
    </label>
  );
}
