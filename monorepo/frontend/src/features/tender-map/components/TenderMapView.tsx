"use client";

import Link from "next/link";
import { useState } from "react";
import { useCompany } from "@/features/company-profile/components/CompanyProvider";
import { toSearchRegion } from "@/features/search/data/profileRegions";
import { SEARCH_REGIONS } from "@/features/search/data/searchConstants";
import { Icon } from "@/features/shared/components/Icon";
import { regionCenter } from "../data/regionCenters";
import { useTenderMap } from "../hooks/useTenderMap";
import { LazyTenderMap } from "./LazyTenderMap";
import { MapLoadError } from "./MapLoadError";

/**
 * Mapa de las direcciones de entrega de las licitaciones abiertas de una zona
 * (HU-22, #314). La zona inicial es la primera región del perfil de la empresa.
 */
export function TenderMapView() {
  const { company } = useCompany();
  const [elegida, setElegida] = useState<string | null>(null);

  const regionesDelPerfil = company.status === "with-company" ? company.supplier.regions : [];
  const zonaDelPerfil =
    regionesDelPerfil.map(toSearchRegion).find((r): r is string => r !== null) ?? null;
  const zona = elegida ?? zonaDelPerfil;
  const centro = zona ? regionCenter(zona) : null;

  const { data, loading, error, retry } = useTenderMap(centro ? zona : null);

  if (company.status === "loading") {
    return (
      <section className="mx-auto w-full max-w-6xl">
        <p className="text-sm text-text-muted">Cargando…</p>
      </section>
    );
  }

  const puntos = data?.items ?? [];

  return (
    <section className="mx-auto flex w-full max-w-6xl flex-col gap-4">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong">
            Mapa de licitaciones
          </h1>
          <p className="mt-2 text-base text-text-muted">
            Dónde hay que entregar lo que piden las licitaciones abiertas de tu zona.
          </p>
        </div>
        <div className="flex flex-col gap-1 sm:w-72">
          <label
            htmlFor="zona-mapa"
            className="text-[10px] font-bold uppercase tracking-caps text-text-subtle"
          >
            Zona
          </label>
          <div className="flex items-center rounded-md border border-border-default bg-white px-3 py-2 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15">
            <Icon name="map-pin" size={15} color="var(--text-subtle)" />
            <select
              id="zona-mapa"
              value={zona ?? ""}
              onChange={(e) => setElegida(e.target.value || null)}
              className="ml-1.5 w-full min-w-0 truncate bg-transparent text-sm text-text-strong outline-none"
            >
              <option value="">Elige una zona</option>
              {SEARCH_REGIONS.map((region) => (
                <option key={region} value={region}>
                  {region}
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      {!centro && (
        <div className="rounded-lg border border-border-subtle bg-surface-card p-6 text-center">
          <p className="text-sm font-medium text-text-strong">
            Elige una zona para ver las licitaciones en el mapa.
          </p>
          <p className="mt-1 text-sm text-text-muted">
            Tu perfil de empresa todavía no tiene una región.{" "}
            <Link
              href={company.status === "with-company" ? "/empresa" : "/perfil"}
              className="font-semibold text-primary hover:text-primary-hover hover:underline"
            >
              Completa tu zona en el perfil
            </Link>{" "}
            para que el mapa la abra directamente.
          </p>
        </div>
      )}

      {centro && error && <MapLoadError onRetry={retry} />}

      {centro && !error && (
        <>
          {loading && <p className="text-sm text-text-muted">Cargando licitaciones…</p>}
          {data && puntos.length === 0 && (
            <div className="rounded-lg border border-border-subtle bg-surface-card p-4 text-sm">
              <p className="font-medium text-text-strong">
                No hay licitaciones con dirección de entrega en {zona}.
              </p>
              <p className="mt-1 text-text-muted">Prueba con otra zona.</p>
            </div>
          )}
          {data?.is_truncated && (
            <p className="text-sm text-text-muted">
              Se muestran {puntos.length} de {data.total} licitaciones: las que cierran
              antes.
            </p>
          )}
          <LazyTenderMap center={centro} points={puntos} />
        </>
      )}
    </section>
  );
}
