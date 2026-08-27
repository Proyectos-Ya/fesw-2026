"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/features/auth/AuthContext";
import { Icon } from "@/features/shared/components/Icon";
import { Button } from "@/features/shared/components/Button";
import { TenderCard } from "@/features/matches/components/TenderCard";
import { TenderCardSkeleton } from "@/features/matches/components/TenderCardSkeleton";
import {
  fetchSavedTenders,
  unsaveTenderApi,
} from "../services/savedTenders.service";
import type { MatchingResult } from "@/features/matches/tenderTypes";
import { ApiError } from "@/features/shared/api/client";

export function SavedTendersList() {
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();
  const [matches, setMatches] = useState<MatchingResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const loadSaved = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSavedTenders();
      setMatches(data);
    } catch (err) {
      console.error(err);
      setError("No pudimos cargar tus licitaciones guardadas.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (authLoading) return;
    if (!isAuthenticated || !user) return;
    void loadSaved();
  }, [authLoading, isAuthenticated, user]);

  const handleToggleSave = async (tenderId: string) => {
    const previous = [...matches];
    setActionError(null);

    setMatches((prev) =>
      prev.filter((m) => (m.tender?.id ?? m.id) !== tenderId)
    );

    try {
      await unsaveTenderApi(tenderId);
    } catch (err) {
      console.error("Error al desguardar:", err);
      setMatches(previous);
      setActionError(
        err instanceof ApiError
          ? err.message
          : "No pudimos retirar la licitación de guardados. Revisa tu conexión."
      );
    }
  };

  if (authLoading || loading) {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <div className="mb-6">
          <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong">
            Licitaciones Guardadas
          </h1>
          <p className="mt-2 text-base text-text-muted">
            Cargando tus licitaciones guardadas...
          </p>
        </div>
        <div className="flex flex-col gap-4">
          <TenderCardSkeleton />
          <TenderCardSkeleton />
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="mx-auto w-full max-w-3xl">
        <div className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center">
          <p className="text-sm font-medium text-danger">{error}</p>
          <Button variant="primary" className="mt-4" onClick={loadSaved}>
            Reintentar
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="mx-auto w-full max-w-3xl">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong">
          Licitaciones Guardadas
        </h1>
        <p className="mt-2 text-base text-text-muted">
          {matches.length === 1
            ? "Tienes 1 licitación guardada para seguimiento."
            : `Tienes ${matches.length} licitaciones guardadas para seguimiento.`}
        </p>
      </div>

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

      {matches.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border-subtle bg-surface-card/50 p-12 text-center">
          <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-primary-soft">
            <Icon name="bookmark" size={24} color="var(--primary)" />
          </div>
          <h2 className="font-display text-xl font-semibold text-text-strong">
            No tienes licitaciones guardadas
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-text-muted">
            Guarda las licitaciones que te interesen para hacer un seguimiento
            rápido desde este panel.
          </p>
          <Link
            href="/matches"
            className="mt-6 inline-flex items-center gap-2 rounded-md bg-primary px-5 py-2.5 text-sm font-bold text-on-primary hover:bg-primary-hover transition-colors"
          >
            Explorar licitaciones
          </Link>
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {matches.map((m) => (
            <TenderCard
              key={m.id}
              match={m}
              isSaved={true}
              onToggleSave={handleToggleSave}
            />
          ))}
        </div>
      )}
    </section>
  );
}