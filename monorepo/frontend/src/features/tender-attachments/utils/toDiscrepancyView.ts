import type { DiscrepancyView } from "@/features/shared/components/DiscrepancyCard";
import type { DigestDiscrepancy } from "../types";

export function toDiscrepancyView(d: DigestDiscrepancy): DiscrepancyView {
  return {
    topic: d.tema,
    description: d.descripcion,
    conflicting_sources: d.fuentes.map((c) => ({
      document_name: c.documento,
      page_or_sheet: c.pagina_u_hoja,
      quote: c.cita,
    })),
  };
}

export function discrepancyReference(
  d: DigestDiscrepancy
): { label: string; value: string } | undefined {
  return d.valor_api
    ? { label: "Mercado Público informa", value: d.valor_api }
    : undefined;
}
