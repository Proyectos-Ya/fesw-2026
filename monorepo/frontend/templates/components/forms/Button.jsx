import React from 'react';

const SIZES = {
  sm: { fontSize: 'var(--text-sm)', padding: '7px 14px', height: 34, gap: 6, radius: 'var(--radius-sm)' },
  md: { fontSize: 'var(--text-base)', padding: '10px 18px', height: 42, gap: 8, radius: 'var(--radius-md)' },
  lg: { fontSize: 'var(--text-lg)', padding: '13px 24px', height: 52, gap: 10, radius: 'var(--radius-md)' },
};

const VARIANTS = {
  primary: {
    rest:  { background: 'var(--primary)', color: 'var(--on-primary)', border: '1px solid transparent', boxShadow: 'var(--shadow-xs)' },
    hover: { background: 'var(--primary-hover)' },
    active:{ background: 'var(--primary-active)' },
  },
  accent: {
    rest:  { background: 'var(--accent)', color: 'var(--on-accent)', border: '1px solid transparent', boxShadow: 'var(--shadow-xs)' },
    hover: { background: 'var(--accent-hover)' },
    active:{ background: 'var(--accent-active)' },
  },
  secondary: {
    rest:  { background: 'var(--surface-card)', color: 'var(--text-strong)', border: '1px solid var(--border-default)', boxShadow: 'var(--shadow-xs)' },
    hover: { background: 'var(--warm-50)', border: '1px solid var(--border-strong)' },
    active:{ background: 'var(--warm-100)' },
  },
  ghost: {
    rest:  { background: 'transparent', color: 'var(--text-body)', border: '1px solid transparent' },
    hover: { background: 'var(--warm-100)' },
    active:{ background: 'var(--warm-200)' },
  },
  soft: {
    rest:  { background: 'var(--primary-soft)', color: 'var(--primary-active)', border: '1px solid transparent' },
    hover: { background: 'var(--teal-100)' },
    active:{ background: 'var(--teal-200)' },
  },
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  iconLeft = null,
  iconRight = null,
  fullWidth = false,
  disabled = false,
  type = 'button',
  onClick,
  style = {},
  ...rest
}) {
  const [hover, setHover] = React.useState(false);
  const [press, setPress] = React.useState(false);
  const s = SIZES[size] || SIZES.md;
  const v = VARIANTS[variant] || VARIANTS.primary;

  const composed = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    gap: s.gap, fontFamily: 'var(--font-sans)', fontWeight: 'var(--weight-semibold)',
    fontSize: s.fontSize, lineHeight: 1, letterSpacing: '-0.005em', whiteSpace: 'nowrap',
    padding: s.padding, minHeight: s.height, borderRadius: s.radius,
    width: fullWidth ? '100%' : 'auto', cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'background var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard)',
    transform: press && !disabled ? 'scale(0.97)' : 'scale(1)',
    opacity: disabled ? 0.5 : 1,
    ...v.rest,
    ...(hover && !disabled ? v.hover : null),
    ...(press && !disabled ? v.active : null),
    ...style,
  };

  return (
    <button
      type={type} disabled={disabled} onClick={onClick} style={composed}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => { setHover(false); setPress(false); }}
      onMouseDown={() => setPress(true)}
      onMouseUp={() => setPress(false)}
      {...rest}
    >
      {iconLeft}
      {children}
      {iconRight}
    </button>
  );
}
