"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSession } from "@/features/auth/components/SessionProvider";
import { Icon } from "@/features/shared/components/Icon";
import { ApiError } from "@/features/shared/api/client";
import { getMySupplier, type Supplier } from "../services/supplierService";

type CompanyState =
  | { status: "loading" }
  | { status: "without-company" }
  | { status: "with-company"; supplier: Supplier }
  | { status: "error" };

function OptionCard({
  href,
  icon,
  title,
  description,
}: {
  href: string;
  icon: string;
  title: string;
  description: string;
}) {
  return (
    <Link
      href={href}
      className="flex flex-col items-start gap-4 rounded-lg bg-white p-8 text-left shadow-premium border border-border-subtle transition-all hover:border-primary hover:shadow-teal hover:scale-[1.01] active:scale-[0.99]"
    >
      <div className="flex size-12 items-center justify-center rounded-full bg-primary-soft">
        <Icon name={icon} size={24} color="var(--primary)" />
      </div>
      <div>
        <h2 className="text-lg font-bold text-text-strong">{title}</h2>
        <p className="mt-1 text-sm text-text-muted leading-relaxed">
          {description}
        </p>
      </div>
    </Link>
  );
}

export function HomeView() {
  const { user } = useSession();
  const [company, setCompany] = useState<CompanyState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;

    getMySupplier()
      .then((supplier) => {
        if (!cancelled) setCompany({ status: "with-company", supplier });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setCompany({ status: "without-company" });
        } else {
          setCompany({ status: "error" });
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (company.status === "loading") return null;

  if (company.status === "error") {
    return (
      <section className="flex flex-1 items-center justify-center py-12">
        <p className="text-text-muted">
          No pudimos cargar tu información. Recarga la página para intentarlo
          nuevamente.
        </p>
      </section>
    );
  }

  if (company.status === "with-company") {
    return (
      <section className="flex flex-1 flex-col items-center justify-center text-center py-12">
        <h1 className="font-display text-4xl font-extrabold tracking-tight text-text-strong max-w-3xl leading-[1.1]">
          Hola{user ? `, ${user.full_name}` : ""}
        </h1>
        <p className="mt-6 max-w-lg text-lg text-text-muted leading-relaxed">
          Tu empresa <strong>{company.supplier.legal_name}</strong> ya tiene su
          perfil listo. Pronto verás aquí tus licitaciones compatibles.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-1 flex-col items-center justify-center text-center py-12">
      <h1 className="font-display text-4xl font-extrabold tracking-tight text-text-strong sm:text-5xl max-w-3xl leading-[1.1]">
        Menos papeleo.<br />
        <span className="text-accent">Más proyectos ganados.</span>
      </h1>
      <p className="mt-6 max-w-lg text-lg text-text-muted leading-relaxed">
        Para empezar a recibir licitaciones compatibles, crea el perfil de tu
        empresa o únete a una existente.
      </p>

      <div className="mt-10 grid w-full max-w-2xl grid-cols-1 gap-6 sm:grid-cols-2">
        <OptionCard
          href="/empresa/crear"
          icon="building-2"
          title="Crear mi empresa"
          description="Construye el perfil inteligente de tu empresa en unos pocos pasos."
        />
        <OptionCard
          href="/empresa/unirse"
          icon="users"
          title="Unirse a una empresa"
          description="¿Tu empresa ya está en ProyectosYA? Pide unirte a su equipo."
        />
      </div>
    </section>
  );
}
