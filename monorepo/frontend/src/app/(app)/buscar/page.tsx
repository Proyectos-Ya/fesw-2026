import React, { Suspense } from "react";
import { SearchDashboard } from "@/features/search/components/SearchDashboard";
import { TenderCardSkeleton } from "@/features/matches/components/TenderCardSkeleton";

function SearchLoadingFallback() {
  return (
    <section className="mx-auto w-full max-w-3xl space-y-6">
      <div>
        <div className="eyebrow mb-2">Buscador Directo</div>
        <h1 className="font-display text-3xl font-bold tracking-tight text-text-strong sm:text-4xl">
          Explorador de Licitaciones
        </h1>
        <p className="mt-2 text-base text-text-muted">
          Cargando explorador...
        </p>
      </div>
      <div className="flex flex-col gap-4 pt-8">
        <TenderCardSkeleton />
        <TenderCardSkeleton />
        <TenderCardSkeleton />
      </div>
    </section>
  );
}

export default function BuscarPage() {
  return (
    <Suspense fallback={<SearchLoadingFallback />}>
      <SearchDashboard />
    </Suspense>
  );
}
