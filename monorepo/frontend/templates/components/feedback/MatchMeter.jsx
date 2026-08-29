import React from 'react';

/** Resolve the brand colour for a compatibility score. */
function scoreColor(v) {
  if (v >= 80) return 'var(--teal-500)';
  if (v >= 60) return 'var(--amber-500)';
  return 'var(--warm-400)';
}

const SIZES = {
  sm: { d: 44, stroke: 5, font: 13 },
  md: { d: 64, stroke: 6, font: 18 },
  lg: { d: 92, stroke: 8, font: 26 },
};

export function MatchMeter({ value = 0, size = 'md', label, showValue = true, style = {} }) {
  const s = SIZES[size] || SIZES.md;
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const r = (s.d - s.stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = scoreColor(v);

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: label ? 12 : 0, fontFamily: 'var(--font-sans)', ...style }}>
      <div style={{ position: 'relative', width: s.d, height: s.d, flex: 'none' }}>
        <svg width={s.d} height={s.d} viewBox={`0 0 ${s.d} ${s.d}`} style={{ transform: 'rotate(-90deg)' }}>
          <circle cx={s.d / 2} cy={s.d / 2} r={r} fill="none" stroke="var(--warm-200)" strokeWidth={s.stroke} />
          <circle cx={s.d / 2} cy={s.d / 2} r={r} fill="none" stroke={color} strokeWidth={s.stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c - (c * v) / 100}
            style={{ transition: 'stroke-dashoffset var(--dur-slow) var(--ease-out)' }} />
        </svg>
        {showValue && (
          <div style={{
            position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-mono)', fontWeight: 600, fontSize: s.font, color: 'var(--text-strong)',
          }}>
            {v}<span style={{ fontSize: '0.6em', marginLeft: 1, color: 'var(--text-subtle)' }}>%</span>
          </div>
        )}
      </div>
      {label && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <span style={{ fontSize: 'var(--text-xs)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600, color: 'var(--text-subtle)' }}>Compatibilidad</span>
          <span style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color }}>{label}</span>
        </div>
      )}
    </div>
  );
}
