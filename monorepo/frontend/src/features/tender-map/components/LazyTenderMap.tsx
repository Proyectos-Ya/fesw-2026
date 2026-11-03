"use client";

import dynamic from "next/dynamic";
import { Component, type ReactNode } from "react";
import type { TenderMapProps } from "./TenderMap";
import { MapLoadError } from "./MapLoadError";

function MapPlaceholder() {
  return (
    <div
      aria-busy="true"
      className="flex h-[70vh] min-h-[420px] w-full items-center justify-center rounded-lg border border-border-subtle bg-surface-card text-sm text-text-muted"
    >
      Cargando mapa…
    </div>
  );
}

// Leaflet usa `window` al importarse, así que el mapa no puede renderizarse en
// el servidor.
const TenderMap = dynamic(() => import("./TenderMap"), {
  ssr: false,
  loading: MapPlaceholder,
});

interface BoundaryState {
  failed: boolean;
}

/**
 * Si el módulo del mapa no llega (red cortada, despliegue nuevo con otro
 * chunk) o Leaflet revienta al montarse, muestra el mismo error que una falla
 * de la API. Reintentar recarga la página: un `import()` que falló queda
 * cacheado y volver a montarlo no lo vuelve a pedir.
 */
class MapLoadBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <MapLoadError onRetry={() => window.location.reload()} />;
    }
    return this.props.children;
  }
}

export function LazyTenderMap(props: TenderMapProps) {
  return (
    <MapLoadBoundary>
      <TenderMap {...props} />
    </MapLoadBoundary>
  );
}
