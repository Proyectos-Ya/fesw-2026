import React from "react";

type ButtonVariant = "primary" | "ghost";

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
    "inline-flex items-center justify-center gap-2 rounded-button px-5 py-2.5 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";
  const variants: Record<ButtonVariant, string> = {
    primary:
      "bg-brand-primary-600 text-white hover:bg-brand-primary-700 active:bg-brand-primary-900",
    ghost: "bg-transparent text-zinc-600 hover:text-brand-primary-700",
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
