import React from 'react';

export function Card({
  children, padding = 20, interactive = false, elevation = 'sm', onClick, style = {}, ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const shadows = { none: 'none', xs: 'var(--shadow-xs)', sm: 'var(--shadow-sm)', md: 'var(--shadow-md)', lg: 'var(--shadow-lg)' };
  const base = shadows[elevation] ?? shadows.sm;
  return (
    <div
      onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        background: 'var(--surface-card)',
        border: '1px solid var(--border-subtle)',
        borderRadius: 'var(--radius-lg)',
        padding, boxShadow: interactive && hover ? 'var(--shadow-md)' : base,
        transform: interactive && hover ? 'translateY(-2px)' : 'translateY(0)',
        cursor: interactive ? 'pointer' : 'default',
        transition: 'box-shadow var(--dur-base) var(--ease-standard), transform var(--dur-base) var(--ease-standard), border-color var(--dur-base) var(--ease-standard)',
        borderColor: interactive && hover ? 'var(--border-default)' : 'var(--border-subtle)',
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  );
}
