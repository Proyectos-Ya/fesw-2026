import { Button } from "@/features/shared/components/Button";

/** El error del criterio 8 de HU-22 (#314), para la API y para el propio mapa. */
export function MapLoadError({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-danger/20 bg-danger-soft/30 p-6 text-center"
    >
      <p className="text-sm font-medium text-danger">No se pudo cargar el mapa</p>
      <Button variant="primary" className="mt-4" onClick={onRetry}>
        Reintentar
      </Button>
    </div>
  );
}
