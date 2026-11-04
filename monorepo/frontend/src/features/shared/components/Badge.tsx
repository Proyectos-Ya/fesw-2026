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
  title?: string;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: "bg-surface-inset text-text-body border-border-subtle",
  teal: "bg-primary-soft text-text-link border-primary-border",
  coral: "bg-accent-soft text-accent border-accent-border",
  success: "bg-success-soft text-success-text border-success/30",
  warning: "bg-warning-soft text-warning-text border-warning/30",
  danger: "bg-danger-soft text-danger-text border-danger/30",
  info: "bg-info-soft text-info-text border-info/30",
  solid: "bg-primary text-on-primary border-transparent",
};

export function Badge({
  children,
  tone = "neutral",
  dot = false,
  iconLeft,
  className = "",
  title,
}: BadgeProps) {
  return (
    <span
      title={title}
      data-tone={tone}
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
