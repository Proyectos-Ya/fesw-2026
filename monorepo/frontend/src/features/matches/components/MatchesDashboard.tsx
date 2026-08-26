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
  filterMatchesByCommune,
  filterMatchesByProvince,
  filterMatchesByRegion,
  isBudgetFilterActive,
  listCommunes,
  listProvinces,
  listRegions,
  type BudgetRange,
} from "../utils/filter";
import { BudgetFilter } from "./BudgetFilter";
import { TenderCard } from "./TenderCard";
import { TenderCardSkeleton } from "./TenderCardSkeleton";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "@/features/saved-tenders/services/savedTenders.service";

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
  const [province, setProvince] = useState<string | null>(null);
  const [commune, setCommune] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [savedTenderIds, setSavedTenderIds] = useState<Set<string>>(new Set());
  const ITEMS_PER_PAGE = 10;
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !user) return;
      fetchSavedTenders()
        .then((saved) => {
          const ids = saved.map(
            (item) => item.tender?.id ?? item.tender_id ?? item.id
          );
          setSavedTenderIds(new Set(ids));
        })
        .catch((err) => console.error("Error al cargar guardadas:", err));
  }, [isAuthenticated, user]);

  const handleRegionChange = (next: string | null) => {
    setRegion(next);
    setProvince(null);
    setCommune(null);
  };

  const handleProvinceChange = (next: string | null) => {
    setProvince(next);
    setCommune(null);
  };

  useEffect(() => {
    setCurrentPage(1);
  }, [budget, region, province, commune]);

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated) {
      window.location.replace("/login");
      return;
    }
    if (!user) return;

    let cancelled = false;
    setState((prev) => (prev.kind === "idle" ? { kind: "loading" } : prev));

    const fetchMatches = async (isBackground = false) => {
      try {
        const matches = await getRecommendedTenders(user.id);
        if (cancelled) return;
        setState({ kind: "ready", matches });
      } catch (err) {
        if (cancelled) return;
        if (!isBackground) {
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
      }
    };

    void fetchMatches(false);

    const intervalId = setInterval(() => {
      void fetchMatches(true);
    }, 180000);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [authLoading, isAuthenticated, user, router, retryNonce]);

  const handleToggleSave = async (tenderId: string) => {
    const isCurrentlySaved = savedTenderIds.has(tenderId);
    setActionError(null);

    // Optimistic update
    setSavedTenderIds((prev) => {
      const next = new Set(prev);
      if (isCurrentlySaved) next.delete(tenderId);
      else next.add(tenderId);
      return next;
    });

    try {
      if (isCurrentlySaved) {
        await unsaveTenderApi(tenderId);
      } else {
        await saveTenderApi(tenderId);
      }
    } catch (err) {
      console.error("Error al actualizar guardado:", err);

      setSavedTenderIds((prev) => {
        const next = new Set(prev);
        if (isCurrentlySaved) next.add(tenderId);
        else next.delete(tenderId);
        return next;
      });

      setActionError(
        err instanceof ApiError
          ? err.message
          : "No pudimos guardar los cambios. Revise su conexión o intente nuevamente."
      );
    }
  };

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
  const filterActive = isBudgetFilterActive(budget) || region !== null || province !== null || commune !== null;
  const visible = filterActive
    ? filterMatchesByCommune(
        filterMatchesByProvince(
          filterMatchesByRegion(filterMatchesByBudget(matches, budget), region),
          province,
        ),
        commune,
      )
    : matches;
  const shown = visible.length;

  const totalPages = Math.ceil(shown / ITEMS_PER_PAGE);
  const paginatedVisible = visible.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

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
      {actionError && (
        <div className="mb-4 flex items-center justify-between rounded-md border border-danger/20 bg-danger-soft/30 p-4 text-sm font-medium text-danger">
          <span>{actionError}</span>
          <button
            type="button"
            onClick={() => setActionError(null)}
            className="text-xs font-bold underline hover:opacity-80 cursor-pointer ml-4"
          >
            Cerrar
          </button>
        </div>
      )}
      {total > 0 && (
        <BudgetFilter
          value={budget}
          onChange={setBudget}
          regions={listRegions(matches)}
          region={region}
          onRegionChange={handleRegionChange}
          provinces={listProvinces(matches, region)}
          province={province}
          onProvinceChange={handleProvinceChange}
          communes={listCommunes(matches, region, province)}
          commune={commune}
          onCommuneChange={setCommune}
        />
      )}
      {total === 0 ? (
        <EmptyMatches />
      ) : shown === 0 ? (
        <EmptyForFilter
          onClear={() => {
            setBudget(EMPTY_BUDGET_RANGE);
            setRegion(null);
            setProvince(null);
            setCommune(null);
          }}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-4">
            {paginatedVisible.map((m) => {
              const tenderId = m.tender?.id ?? m.id;
              return (
                <TenderCard
                  key={m.id}
                  match={m}
                  isSaved={savedTenderIds.has(tenderId)}
                  onToggleSave={handleToggleSave}
                />
              );
            })}
          </div>
          {totalPages > 1 && (
            <div className="mt-6 flex items-center justify-between border-t border-border-subtle pt-6">
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-card px-4 py-2 text-sm font-semibold text-text-strong hover:bg-surface-hover disabled:opacity-50 disabled:hover:bg-surface-card transition-colors cursor-pointer disabled:cursor-not-allowed"
              >
                <Icon name="chevron-left" size={16} />
                Anterior
              </button>
              <span className="text-sm font-medium text-text-muted">
                Página {currentPage} de {totalPages}
              </span>
              <button
                type="button"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="inline-flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-card px-4 py-2 text-sm font-semibold text-text-strong hover:bg-surface-hover disabled:opacity-50 disabled:hover:bg-surface-card transition-colors cursor-pointer disabled:cursor-not-allowed"
              >
                Siguiente
                <Icon name="chevron-right" size={16} />
              </button>
            </div>
          )}
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