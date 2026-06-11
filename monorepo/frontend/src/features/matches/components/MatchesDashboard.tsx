"use client";

/* eslint-disable react-hooks/set-state-in-effect -- bootstrap fetch + retry use the canonical effect+cancel pattern. */

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/features/auth/AuthContext";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { getRecommendedTenders } from "../services/tenderService";
import type { MatchingResult } from "../tenderTypes";
import {
  EMPTY_BUDGET_RANGE,
  filterMatchesByBudget,
  filterMatchesByRegion,
  isBudgetFilterActive,
  listRegions,
  type BudgetRange,
} from "../utils/filter";
import { BudgetFilter } from "./BudgetFilter";
import { TenderCard } from "./TenderCard";
import { TenderCardSkeleton } from "./TenderCardSkeleton";

type LoadState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; matches: MatchingResult[] }
  | { kind: "no-supplier" }
  | { kind: "error"; message: string };

function isSupplierMissing(err: ApiError): boolean {
  return err.status === 404;
}

export function MatchesDashboard() {
  const router = useRouter();
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [state, setState] = useState<LoadState>({ kind: "idle" });
  const [retryNonce, setRetryNonce] = useState(0);
  const [budget, setBudget] = useState<BudgetRange>(EMPTY_BUDGET_RANGE);
  const [region, setRegion] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      router.replace("/login");
      return;
    }
    if (!user) return;

    let cancelled = false;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const matches = await getRecommendedTenders(user.id);
        if (cancelled) return;
        setState({ kind: "ready", matches });
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && isSupplierMissing(err)) {
          setState({ kind: "no-supplier" });
          return;
        }
        if (err instanceof ApiError || err instanceof TimeoutError) {
          setState({ kind: "error", message: err.message });
          return;
        }
        setState({
          kind: "error",
          message: "No pudimos cargar tus matches. Inténtalo nuevamente.",
        });
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, isAuthenticated, user, router, retryNonce]);

  const handleRetry = () => setRetryNonce((n) => n + 1);

  if (authLoading || state.kind === "idle" || state.kind === "loading") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <DashboardHeader countLine="Buscando licitaciones que calzan con tu perfil…" />
        <div className="flex flex-col gap-4">
          <TenderCardSkeleton />
          <TenderCardSkeleton />
          <TenderCardSkeleton />
        </div>
      </section>
    );
  }

  if (state.kind === "no-supplier") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <DashboardHeader countLine="Aún no tenemos tu perfil para hacer matching." />
        <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary-soft">
            <Icon name="sparkles" size={22} color="var(--primary)" />
          </div>
          <h2 className="font-display text-2xl font-bold text-text-strong">
            Primero crea tu perfil inteligente
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            Necesitamos saber el rubro, regiones y experiencia de tu empresa para mostrarte
            licitaciones que realmente calcen.
          </p>
          <Link
            href="/perfil"
            className="mt-6 inline-flex items-center gap-2 rounded-full bg-primary px-6 py-3 text-sm font-bold text-on-primary shadow-teal hover:bg-primary-hover transition-colors"
          >
            Construir mi perfil
            <Icon name="arrow-right" size={16} />
          </Link>
        </div>
      </section>
    );
  }

  if (state.kind === "error") {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <DashboardHeader countLine="No pudimos cargar tus matches." />
        <div className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center">
          <p className="text-sm font-medium text-danger">{state.message}</p>
          <Button
            variant="primary"
            className="mt-4"
            onClick={handleRetry}
          >
            Reintentar
          </Button>
        </div>
      </section>
    );
  }

  const { matches } = state;
  const total = matches.length;
  const filterActive = isBudgetFilterActive(budget) || region !== null;
  const visible = filterActive
    ? filterMatchesByRegion(filterMatchesByBudget(matches, budget), region)
    : matches;
  const shown = visible.length;

  let countLine: string;
  if (total === 0) {
    countLine = "Aún no hay matches nuevos. Vuelve a revisar en unas horas.";
  } else if (filterActive) {
    countLine =
      shown === total
        ? `Mostrando ${shown} de ${total} licitaciones.`
        : `Mostrando ${shown} de ${total} licitaciones según tus filtros.`;
  } else {
    countLine =
      total === 1
        ? "Encontramos 1 licitación que calza con tu perfil."
        : `Encontramos ${total} licitaciones que calzan con tu perfil.`;
  }

  return (
    <section className="mx-auto w-full max-w-3xl">
      <DashboardHeader countLine={countLine} />
      {total > 0 && (
        <BudgetFilter
          value={budget}
          onChange={setBudget}
          regions={listRegions(matches)}
          region={region}
          onRegionChange={setRegion}
        />
      )}
      {total === 0 ? (
        <EmptyMatches />
      ) : shown === 0 ? (
        <EmptyForFilter
          onClear={() => {
            setBudget(EMPTY_BUDGET_RANGE);
            setRegion(null);
          }}
        />
      ) : (
        <div className="flex flex-col gap-4">
          {visible.map((m) => (
            <TenderCard key={m.id} match={m} />
          ))}
        </div>
      )}
    </section>
  );
}

function EmptyForFilter({ onClear }: { onClear: () => void }) {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-warm-100">
        <Icon name="sliders-horizontal" size={22} color="var(--text-subtle)" />
      </div>
      <h2 className="font-display text-xl font-semibold text-text-strong">
        Ninguna licitación coincide con tus filtros
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
        Ajusta la ubicación o el rango de presupuesto, o límpialos para volver a
        ver todos tus matches.
      </p>
      <button
        type="button"
        onClick={onClear}
        className="mt-5 inline-flex items-center gap-1.5 rounded-md bg-primary-soft px-4 py-2 text-sm font-bold text-primary hover:bg-teal-100 transition-colors"
      >
        Limpiar filtros
      </button>
    </div>
  );
}

function DashboardHeader({ countLine }: { countLine: string }) {
  return (
    <div className="mb-6">
      <div className="eyebrow mb-2">Para ti</div>
      <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong sm:text-4xl">
        Licitaciones que calzan con tu perfil
      </h1>
      <p className="mt-2 text-base text-text-muted">{countLine}</p>
    </div>
  );
}

function EmptyMatches() {
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-10 text-center shadow-xs">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-warm-100">
        <Icon name="search" size={22} color="var(--text-subtle)" />
      </div>
      <h2 className="font-display text-xl font-semibold text-text-strong">
        Sin matches por ahora
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
        Cuando publiquemos licitaciones que calcen con tu rubro y regiones, las verás
        ordenadas por compatibilidad acá.
      </p>
    </div>
  );
}
