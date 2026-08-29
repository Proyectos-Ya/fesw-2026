import React from 'react';

export function Input({
  label, hint, error, iconLeft = null, value, onChange, placeholder,
  type = 'text', disabled = false, id, style = {}, ...rest
}) {
  const [focus, setFocus] = React.useState(false);
  const autoId = React.useId();
  const fieldId = id || autoId;
  const borderColor = error ? 'var(--danger)' : focus ? 'var(--primary)' : 'var(--border-default)';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontFamily: 'var(--font-sans)', ...style }}>
      {label && (
        <label htmlFor={fieldId} style={{ fontSize: 'var(--text-sm)', fontWeight: 'var(--weight-medium)', color: 'var(--text-body)' }}>
          {label}
        </label>
      )}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: disabled ? 'var(--surface-inset)' : 'var(--surface-card)',
        border: `1px solid ${borderColor}`, borderRadius: 'var(--radius-md)',
        padding: '0 12px', height: 44,
        boxShadow: focus ? `0 0 0 3px ${error ? 'var(--ring-accent)' : 'var(--ring)'}` : 'none',
        transition: 'border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)',
      }}>
        {iconLeft && <span style={{ color: 'var(--text-subtle)', display: 'inline-flex' }}>{iconLeft}</span>}
        <input
          id={fieldId} type={type} value={value} onChange={onChange} placeholder={placeholder} disabled={disabled}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={{
            flex: 1, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: 'var(--font-sans)', fontSize: 'var(--text-base)', color: 'var(--text-strong)',
            minWidth: 0,
          }}
          {...rest}
        />
      </div>
      {(hint || error) && (
        <span style={{ fontSize: 'var(--text-xs)', color: error ? 'var(--danger)' : 'var(--text-subtle)' }}>
          {error || hint}
        </span>
      )}
    </div>
  );
}
