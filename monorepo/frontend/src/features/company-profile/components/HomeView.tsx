"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";

function HomeContent() {
  const params = useSearchParams();
  const as = params.get("as");
  const isLoggedIn = as === "new" || as === "ready";
  const hasProfile = as === "ready";

  if (!isLoggedIn || hasProfile) return null;

  return (
    <section className="flex flex-1 flex-col items-center justify-center text-center py-12">
      <h1 className="font-display text-4xl font-extrabold tracking-tight text-text-strong sm:text-5xl lg:text-6xl max-w-3xl leading-[1.1]">
        Menos papeleo.<br />
        <span className="text-accent">Más proyectos ganados.</span>
      </h1>
      <p className="mt-6 max-w-lg text-lg text-text-muted leading-relaxed">
        Crea tu perfil inteligente para empezar a recibir licitaciones que realmente coincidan con tu negocio.
      </p>
      <Link
        href="/perfil"
        className="mt-10 rounded-full bg-primary px-10 py-4 text-base font-bold text-white shadow-teal transition-all hover:bg-primary-hover hover:scale-[1.02] active:scale-[0.98]"
      >
        Construir mi perfil inteligente
      </Link>
    </section>
  );
}

export function HomeView() {
  return (
    <Suspense fallback={null}>
      <HomeContent />
    </Suspense>
  );
}
