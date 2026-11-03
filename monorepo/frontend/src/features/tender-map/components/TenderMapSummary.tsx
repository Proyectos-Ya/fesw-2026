import Link from "next/link";
import { formatClosingDate } from "@/features/matches/utils/format";
import type { TenderMapPoint } from "../types";

interface TenderMapSummaryProps {
  point: TenderMapPoint;
}

/** Resumen de la licitación al hacer clic en un marcador (HU-22, #314). */
export function TenderMapSummary({ point }: TenderMapSummaryProps) {
  return (
    <div className="flex w-64 flex-col gap-2 text-text-body">
      <p className="text-sm font-semibold leading-snug text-text-strong">{point.name}</p>
      <dl className="flex flex-col gap-1 text-xs">
        <div>
          <dt className="text-text-muted">Organismo</dt>
          <dd>{point.buyer_name ?? "Organismo no informado"}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Dirección de entrega</dt>
          <dd>{point.delivery_address}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Cierre</dt>
          <dd className="font-mono">{formatClosingDate(point.closing_at)}</dd>
        </div>
      </dl>
      {point.precision === "comuna" && (
        <p className="text-xs text-text-subtle">
          Ubicación aproximada: no encontramos la dirección y marcamos la comuna del
          organismo.
        </p>
      )}
      <Link
        href={`/matches/${point.id}`}
        className="text-xs font-semibold text-primary hover:text-primary-hover hover:underline"
      >
        Ver detalle
      </Link>
    </div>
  );
}
