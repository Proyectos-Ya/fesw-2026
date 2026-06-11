"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/features/auth/AuthContext";
import { useCompany } from "./CompanyProvider";
import { Icon } from "@/features/shared/components/Icon";

/** Placeholder de licitaciones mientras no exista el matching real. */
function TenderListPlaceholder({ companyName }: { companyName: string }) {
  return (
    <section className="flex flex-1 flex-col py-4">
      <div className="eyebrow mb-2">Licitaciones</div>
      <h1 className="font-display text-3xl font-extrabold tracking-tight text-text-strong">
        Recomendadas para {companyName}
      </h1>
      <p className="mt-2 text-text-muted">
        Aquí aparecerán las licitaciones compatibles con el perfil de tu
        empresa.
      </p>

      <div className="mt-8 flex flex-col gap-4">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-lg border border-border-subtle bg-white p-6 shadow-xs"
          >
            <div className="flex items-center gap-3">
              <div className="flex size-10 flex-none items-center justify-center rounded-full bg-primary-soft">
                <Icon name="file-text" size={20} color="var(--primary)" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="h-4 w-2/3 rounded bg-warm-100" />
                <div className="mt-2 h-3 w-1/3 rounded bg-warm-100" />
              </div>
              <span className="rounded-full bg-warm-100 px-3 py-1 text-xs font-bold text-text-subtle">
                Próximamente
              </span>
            </div>
          </div>
        ))}
      </div>

      <p className="mt-6 text-sm text-text-subtle">
        Estamos preparando tus primeros matches. Vuelve pronto.
      </p>
    </section>
  );
}

export function HomeView() {
  const router = useRouter();
  const { user, isLoading, isAuthenticated } = useAuth();
  const { company } = useCompany();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.replace("/login");
    }
  }, [isLoading, isAuthenticated, router]);

  if (isLoading || !isAuthenticated || company.status === "loading") {
    return (
      <section className="flex flex-1 items-center justify-center py-12">
        <span className="text-sm text-text-subtle">Cargando…</span>
      </section>
    );
  }

  if (company.status === "error") {
    return (
      <section className="flex flex-1 flex-col items-center justify-center py-12 text-center">
        <p className="text-text-muted">
          No pudimos cargar tu información. Intenta recargar la página.
        </p>
      </section>
    );
  }

  if (company.status === "with-company") {
    return <TenderListPlaceholder companyName={company.supplier.legal_name} />;
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
        Para empezar a recibir licitaciones compatibles, crea el perfil de tu
        empresa o únete a una existente.
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
