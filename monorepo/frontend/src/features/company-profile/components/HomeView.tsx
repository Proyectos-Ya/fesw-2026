"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/features/auth/AuthContext";

export function HomeView() {
  const router = useRouter();
  const { user, isLoading, isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <section className="flex flex-1 items-center justify-center py-12">
        <span className="text-sm text-text-subtle">Cargando…</span>
      </section>
    );
  }

  const firstName = user?.full_name?.split(/\s+/)[0] ?? "";

  return (
    <section className="flex flex-1 flex-col items-center justify-center text-center py-12">
      <div className="eyebrow mb-3">Bienvenido</div>
      <h1 className="font-display text-4xl font-extrabold tracking-tight text-text-strong sm:text-5xl lg:text-6xl max-w-3xl leading-[1.1]">
        Hola{firstName ? `, ${firstName}` : ""}.<br />
        <span className="text-accent">Menos papeleo, más proyectos.</span>
      </h1>
      <p className="mt-6 max-w-lg text-lg text-text-muted leading-relaxed">
        Crea tu perfil inteligente para empezar a recibir licitaciones que realmente coincidan con tu negocio.
      </p>
      <Link
        href="/perfil"
        className="mt-10 rounded-full bg-primary px-10 py-4 text-base font-bold text-on-primary shadow-teal transition-all hover:bg-primary-hover hover:scale-[1.02] active:scale-[0.98]"
      >
        Construir mi perfil inteligente
      </Link>
    </section>
  );
}
