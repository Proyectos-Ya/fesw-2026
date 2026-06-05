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
    <section className="flex flex-1 flex-col items-center justify-center text-center">
      <h1 className="font-display text-3xl font-semibold text-brand-primary-900 sm:text-4xl">
        Aún no has creado tu perfil de marca inteligente
      </h1>
      <p className="mt-4 max-w-md text-zinc-600">
        Constrúyelo para empezar a recibir licitaciones que coincidan con tu negocio.
      </p>
      <Link
        href="/perfil"
        className="mt-10 rounded-button bg-brand-primary-600 px-8 py-3 text-base font-medium text-white transition-colors hover:bg-brand-primary-700"
      >
        Comenzar
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
