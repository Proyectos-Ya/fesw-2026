import type { ReactNode } from "react";

export type BadgeTone =
  | "neutral"
  | "teal"
  | "coral"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "solid";

interface BadgeProps {
  children: ReactNode;
  tone?: BadgeTone;
  dot?: boolean;
  iconLeft?: ReactNode;
  className?: string;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-warm-100 text-warm-700 border-warm-200",
  teal: "bg-teal-50 text-teal-700 border-teal-200",
  coral: "bg-coral-50 text-coral-700 border-coral-200",
  success: "bg-success-soft text-green-600 border-transparent",
  warning: "bg-warning-soft text-amber-600 border-transparent",
  danger: "bg-danger-soft text-red-600 border-transparent",
  info: "bg-info-soft text-blue-500 border-transparent",
  solid: "bg-primary text-on-primary border-transparent",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  iconLeft,
  className = "",
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold leading-none whitespace-nowrap ${TONE_CLASSES[tone]} ${className}`}
    >
      {dot && (
        <span
          aria-hidden="true"
          className="size-1.5 rounded-full bg-current"
        />
      )}
      {iconLeft}
      {children}
    </span>
  );
}
