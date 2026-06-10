import React from 'react';

const SIZES = { sm: 34, md: 42, lg: 48 };

export function IconButton({
  icon, label, variant = 'secondary', size = 'md', disabled = false, onClick, style = {}, ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [press, setPress] = React.useState(false);
  const dim = SIZES[size] || SIZES.md;

  const variants = {
    primary:   { background: 'var(--primary)', color: 'var(--on-primary)', border: '1px solid transparent', hover: 'var(--primary-hover)' },
    secondary: { background: 'var(--surface-card)', color: 'var(--text-body)', border: '1px solid var(--border-default)', hover: 'var(--warm-50)' },
    ghost:     { background: 'transparent', color: 'var(--text-muted)', border: '1px solid transparent', hover: 'var(--warm-100)' },
  };
  const v = variants[variant] || variants.secondary;

  return (
    <button
      type="button" aria-label={label} disabled={disabled} onClick={onClick}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => { setHover(false); setPress(false); }}
      onMouseDown={() => setPress(true)} onMouseUp={() => setPress(false)}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        width: dim, height: dim, borderRadius: 'var(--radius-md)',
        background: hover && !disabled ? v.hover : v.background, color: v.color, border: v.border,
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        transform: press && !disabled ? 'scale(0.94)' : 'scale(1)',
        transition: 'background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard)',
        ...style,
      }}
      {...rest}
    >
      {icon}
    </button>
  );
}
