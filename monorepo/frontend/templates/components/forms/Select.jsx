import React from 'react';

export function Select({ label, hint, value, onChange, options = [], placeholder, disabled = false, id, style = {} }) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const fieldId = id || autoId;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-sans)', ...style }}>
      {label && <label htmlFor={fieldId} style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)', color: 'var(--text-body)' }}>{label}</label>}
      <div style={{ position: 'relative' }}>
        <select
          id={fieldId} value={value} disabled={disabled}
          onChange={(e) => onChange && onChange(e.target.value, e)}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{
            width: '100%', appearance: 'none', WebkitAppearance: 'none',
            height: 44, padding: '0 40px 0 12px', borderRadius: 'var(--radius-md)',
            background: disabled ? 'var(--surface-inset)' : 'var(--surface-card)',
            border: `1px solid ${focus ? 'var(--primary)' : 'var(--border-default)'}`,
            boxShadow: focus ? '0 0 0 3px var(--ring)' : 'none',
            fontFamily: 'var(--font-sans)', fontSize: 'var(--text-base)',
            color: value ? 'var(--text-strong)' : 'var(--text-subtle)',
            cursor: disabled ? 'not-allowed' : 'pointer', outline: 'none',
            transition: 'border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)',
          }}
        >
          {placeholder && <option value="" disabled hidden>{placeholder}</option>}
          {options.map((o) => {
            const val = typeof o === 'string' ? o : o.value;
            const lab = typeof o === 'string' ? o : o.label;
            return <option key={val} value={val}>{lab}</option>;
          })}
        </select>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--text-subtle)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
          style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none' }}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </div>
      {hint && <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-subtle)' }}>{hint}</span>}
    </div>
  );
}
