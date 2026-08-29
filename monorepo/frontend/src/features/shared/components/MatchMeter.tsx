import type { CSSProperties } from "react";

type MatchMeterSize = "sm" | "md" | "lg";

interface MatchMeterThresholds {
  high: number;
  mid: number;
}

interface MatchMeterColors {
  high: string;
  mid: string;
  low: string;
}

interface MatchMeterProps {
  value: number;
  size?: MatchMeterSize;
  label?: string;
  showValue?: boolean;
  thresholds?: MatchMeterThresholds;
  colors?: MatchMeterColors;
  className?: string;
  style?: CSSProperties;
}

const SIZES: Record<MatchMeterSize, { d: number; stroke: number; font: number }> = {
  sm: { d: 44, stroke: 5, font: 13 },
  md: { d: 64, stroke: 6, font: 18 },
  lg: { d: 92, stroke: 8, font: 26 },
};

const DEFAULT_THRESHOLDS: MatchMeterThresholds = { high: 80, mid: 60 };
const DEFAULT_COLORS: MatchMeterColors = {
  high: "var(--teal-500)",
  mid: "var(--amber-500)",
  low: "var(--warm-400)",
};

function scoreColor(v: number, t: MatchMeterThresholds, c: MatchMeterColors): string {
  if (v >= t.high) return c.high;
  if (v >= t.mid) return c.mid;
  return c.low;
}

export function MatchMeter({
  value,
  size = "md",
  label,
  showValue = true,
  thresholds = DEFAULT_THRESHOLDS,
  colors = DEFAULT_COLORS,
  className = "",
  style,
}: MatchMeterProps) {
  const s = SIZES[size];
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const r = (s.d - s.stroke) / 2;
  const c = 2 * Math.PI * r;
  const color = scoreColor(v, thresholds, colors);
  const cx = s.d / 2;

  return (
    <div
      className={`inline-flex items-center font-sans ${className}`}
      style={{ gap: label ? 12 : 0, ...style }}
    >
      <div className="relative flex-none" style={{ width: s.d, height: s.d }}>
        <svg
          width={s.d}
          height={s.d}
          viewBox={`0 0 ${s.d} ${s.d}`}
          style={{ transform: "rotate(-90deg)" }}
          aria-hidden={label ? "true" : undefined}
          role={label ? undefined : "img"}
          aria-label={label ? undefined : `Compatibilidad ${v}%`}
        >
          <circle cx={cx} cy={cx} r={r} fill="none" stroke="var(--warm-200)" strokeWidth={s.stroke} />
          <circle
            cx={cx}
            cy={cx}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth={s.stroke}
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={c - (c * v) / 100}
            style={{ transition: "stroke-dashoffset 700ms cubic-bezier(0.16, 1, 0.3, 1)" }}
          />
        </svg>
        {showValue && (
          <div
            className="absolute inset-0 flex items-center justify-center font-mono font-semibold text-text-strong"
            style={{ fontSize: s.font }}
          >
            {v}
            <span className="ml-[1px] text-text-subtle" style={{ fontSize: "0.6em" }}>
              %
            </span>
          </div>
        )}
      </div>
      {label && (
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-semibold uppercase tracking-caps text-text-subtle">
            Compatibilidad
          </span>
          <span className="text-sm font-semibold" style={{ color }}>
            {label}
          </span>
        </div>
      )}
    </div>
  );
}
