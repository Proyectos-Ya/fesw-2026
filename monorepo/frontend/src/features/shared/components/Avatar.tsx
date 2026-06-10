import React from "react";

const SIZES = { xs: 24, sm: 32, md: 40, lg: 56 };
const PALETTE = [
  "var(--teal-500)",
  "var(--coral-500)",
  "var(--teal-700)",
  "var(--amber-500)",
  "var(--blue-500)",
  "var(--green-500)",
];

function initials(name = "") {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((w) => w[0] || "")
    .join("")
    .toUpperCase();
}

interface AvatarProps {
  name?: string;
  src?: string;
  size?: keyof typeof SIZES;
  shape?: "circle" | "square";
  className?: string;
}

export function Avatar({
  name = "",
  src,
  size = "md",
  shape = "circle",
  className = "",
}: AvatarProps) {
  const dim = SIZES[size] || SIZES.md;
  const radius = shape === "square" ? "var(--radius-md)" : "50%";
  const idx = name ? name.charCodeAt(0) % PALETTE.length : 0;

  return (
    <span
      className={`inline-flex items-center justify-center flex-none overflow-hidden select-none font-sans font-semibold ${className}`}
      style={{
        width: dim,
        height: dim,
        borderRadius: radius,
        background: src ? "var(--warm-200)" : PALETTE[idx],
        color: "var(--white)",
        fontSize: dim * 0.4,
        letterSpacing: "0.01em",
      }}
    >
      {src ? (
        <img
          src={src}
          alt={name}
          className="w-full h-full object-cover"
        />
      ) : (
        initials(name)
      )}
    </span>
  );
}
