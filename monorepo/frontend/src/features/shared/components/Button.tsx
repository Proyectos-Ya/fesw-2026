import React from "react";

type ButtonVariant = "primary" | "ghost" | "accent";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  isLoading?: boolean;
}

export function Button({
  variant = "primary",
  isLoading = false,
  children,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 active:scale-[0.98]";
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-primary text-on-primary shadow-teal hover:bg-primary-hover active:bg-primary-active",
    accent:
      "bg-accent text-white shadow-coral hover:bg-accent-hover active:bg-accent-active",
    ghost: "bg-transparent text-text-muted hover:text-primary hover:bg-primary-soft",
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${className}`}
      disabled={disabled ?? isLoading}
      {...props}
    >
      {isLoading ? (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
      ) : null}
      {children}
    </button>
  );
}
