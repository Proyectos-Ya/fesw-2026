"use client";

import { useEffect, useState } from "react";

const REDIRECT_DELAY_MS = 2500;

interface SuccessViewProps {
  onRedirect: () => void;
}

export function SuccessView({ onRedirect }: SuccessViewProps) {
  const [started, setStarted] = useState(false);

  useEffect(() => {
    // Trigger the progress bar drain on the next frame so the CSS transition fires
    const raf = requestAnimationFrame(() => setStarted(true));
    const timer = setTimeout(onRedirect, REDIRECT_DELAY_MS);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [onRedirect]);

  return (
    <div className="flex flex-col items-center justify-center gap-6 py-12 text-center">
      {/* Animated checkmark */}
      <div className="flex h-20 w-20 items-center justify-center rounded-full bg-success-soft">
        <svg
          className="h-10 w-10 text-success"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle
            cx={12}
            cy={12}
            r={10}
            className="opacity-30"
          />
          <path
            d="M7 13l3 3 7-7"
            style={{
              strokeDasharray: 20,
              strokeDashoffset: started ? 0 : 20,
              transition: "stroke-dashoffset 0.5s ease-out 0.1s",
            }}
          />
        </svg>
      </div>

      <div className="flex flex-col gap-1.5">
        <h2 className="font-display text-2xl font-bold text-text-primary">
          ¡Perfil creado con éxito!
        </h2>
        <p className="text-sm text-text-muted">Redirigiendo a tu dashboard…</p>
      </div>

      {/* Drain bar */}
      <div className="h-1 w-48 overflow-hidden rounded-full bg-border-subtle/50">
        <div
          className="h-full rounded-full bg-primary"
          style={{
            width: started ? "0%" : "100%",
            transition: `width ${REDIRECT_DELAY_MS}ms linear`,
          }}
        />
      </div>
    </div>
  );
}
