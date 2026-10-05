import { AlertCircle, Bot, RefreshCw } from "lucide-react";

import { Badge } from "@/features/shared/components/Badge";
import { DiscrepancyCard } from "@/features/shared/components/DiscrepancyCard";
import { useTenderDigest } from "../hooks/useTenderDigest";
import { AI_NOTICE } from "../types";
import { formatBudget, formatDigestDate, formatVisit } from "../utils/formatDigest";
import { discrepancyReference, toDiscrepancyView } from "../utils/toDiscrepancyView";
import { DigestCitations } from "./DigestCitations";

interface DigestCardProps {
  tenderId: string;
  refreshKey: string;
}

export function DigestCard({ tenderId, refreshKey }: DigestCardProps) {
  const { state, reload } = useTenderDigest(tenderId, refreshKey);

  if (state.status === "loading") {
    return (
      <div
        role="status"
        className="flex items-center gap-2 rounded-lg border border-warm-200 bg-white p-4 text-xs text-text-muted shadow-xs"
      >
        <RefreshCw className="h-4 w-4 animate-spin text-primary" />
        <span>Cargando el resumen de los anexos…</span>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div
        role="alert"
        className="flex items-center justify-between rounded-lg border border-red-200 bg-red-50 p-4 text-xs text-red-900"
      >
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-600" />
          <span>{state.message}</span>
        </div>
        <button
          type="button"
          onClick={reload}
          className="font-semibold text-red-700 hover:underline"
        >
          Reintentar
        </button>
      </div>
    );
  }

  const digest = state.data;
  if (digest.status === "empty") {
    return (
      <section
        aria-labelledby="digest-heading"
        className="rounded-lg border border-warm-200 bg-white p-4 text-xs text-text-muted shadow-xs"
      >
        <h3 id="digest-heading" className="font-semibold text-slate-800">
          Resumen de los anexos
        </h3>
        <p className="mt-2">Todavía no hay anexos procesados para resumir.</p>
      </section>
    );
  }

  const { data } = digest;
  const { campos, discrepancias, requisitos, items, entregables, puntos_a_tener_en_cuenta, resumenes, fuentes } = data;

  return (
    <section
      aria-labelledby="digest-heading"
      className="flex flex-col gap-4 rounded-xl border border-warm-200 bg-white p-5 text-xs text-slate-800 shadow-xs"
    >
      {/* 1. Encabezado y aviso de IA */}
      <div className="flex flex-col gap-1.5 border-b border-warm-200/80 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="digest-heading" className="text-sm font-bold text-slate-900">
            Resumen de los anexos
          </h3>
          <Badge tone="info" iconLeft={<Bot className="h-3 w-3" />}>
            Generado con IA
          </Badge>
        </div>
        <p className="text-[11px] text-text-muted leading-relaxed">{AI_NOTICE}</p>
        {digest.scope === "workspace" && (
          <p className="text-[11px] font-medium text-amber-700">
            Incluye anexos que solo ve tu empresa.
          </p>
        )}
        {digest.pending_sources > 0 && (
          <p className="text-[11px] text-blue-700">
            Todavía estamos leyendo {digest.pending_sources} anexo(s).
          </p>
        )}
      </div>

      {/* 2. Discrepancias primero */}
      {discrepancias && discrepancias.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">
            Discrepancias detectadas
          </h4>
          <div className="flex flex-col gap-2">
            {discrepancias.map((d, index) => (
              <DiscrepancyCard
                key={`${d.tema}-${index}`}
                discrepancy={toDiscrepancyView(d)}
                reference={discrepancyReference(d)}
              />
            ))}
          </div>
        </div>
      )}

      {/* 3. Fechas y presupuesto */}
      <div className="flex flex-col gap-2">
        <h4 className="font-bold text-slate-900 text-xs">Fechas y presupuesto</h4>
        <dl className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {campos.presupuesto && (
            <div className="rounded-md border border-warm-200/60 bg-warm-50/50 p-2.5">
              <dt className="font-semibold text-slate-700">Presupuesto</dt>
              <dd className="mt-0.5 text-slate-900">
                {campos.presupuesto.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-amber-800">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[11px]">
                      {campos.presupuesto.alternativas.map((a, i) => (
                        <li key={i}>{formatBudget(a.valor)}</li>
                      ))}
                    </ul>
                  </div>
                ) : campos.presupuesto.valor ? (
                  formatBudget(campos.presupuesto.valor)
                ) : null}
                <DigestCitations citas={campos.presupuesto.citas} />
              </dd>
            </div>
          )}

          {campos.fecha_publicacion && (
            <div className="rounded-md border border-warm-200/60 bg-warm-50/50 p-2.5">
              <dt className="font-semibold text-slate-700">Publicación</dt>
              <dd className="mt-0.5 text-slate-900">
                {campos.fecha_publicacion.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-amber-800">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[11px]">
                      {campos.fecha_publicacion.alternativas.map((a, i) => (
                        <li key={i}>{formatDigestDate(a.valor)}</li>
                      ))}
                    </ul>
                  </div>
                ) : campos.fecha_publicacion.valor ? (
                  formatDigestDate(campos.fecha_publicacion.valor)
                ) : null}
                <DigestCitations citas={campos.fecha_publicacion.citas} />
              </dd>
            </div>
          )}

          {campos.fecha_cierre_primer_llamado && (
            <div className="rounded-md border border-warm-200/60 bg-warm-50/50 p-2.5">
              <dt className="font-semibold text-slate-700">
                Cierre del primer llamado
              </dt>
              <dd className="mt-0.5 text-slate-900">
                {campos.fecha_cierre_primer_llamado.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-amber-800">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[11px]">
                      {campos.fecha_cierre_primer_llamado.alternativas.map(
                        (a, i) => (
                          <li key={i}>{formatDigestDate(a.valor)}</li>
                        )
                      )}
                    </ul>
                  </div>
                ) : campos.fecha_cierre_primer_llamado.valor ? (
                  formatDigestDate(campos.fecha_cierre_primer_llamado.valor)
                ) : null}
                <DigestCitations citas={campos.fecha_cierre_primer_llamado.citas} />
              </dd>
            </div>
          )}

          {campos.fecha_cierre_segundo_llamado && (
            <div className="rounded-md border border-warm-200/60 bg-warm-50/50 p-2.5">
              <dt className="font-semibold text-slate-700">
                Cierre del segundo llamado
              </dt>
              <dd className="mt-0.5 text-slate-900">
                {campos.fecha_cierre_segundo_llamado.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-amber-800">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[11px]">
                      {campos.fecha_cierre_segundo_llamado.alternativas.map(
                        (a, i) => (
                          <li key={i}>{formatDigestDate(a.valor)}</li>
                        )
                      )}
                    </ul>
                  </div>
                ) : campos.fecha_cierre_segundo_llamado.valor ? (
                  formatDigestDate(campos.fecha_cierre_segundo_llamado.valor)
                ) : null}
                <DigestCitations citas={campos.fecha_cierre_segundo_llamado.citas} />
              </dd>
            </div>
          )}

          {campos.visita_tecnica && (
            <div className="rounded-md border border-warm-200/60 bg-warm-50/50 p-2.5 sm:col-span-2">
              <dt className="font-semibold text-slate-700">Visita técnica</dt>
              <dd className="mt-0.5 text-slate-900">
                {campos.visita_tecnica.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-amber-800">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[11px]">
                      {campos.visita_tecnica.alternativas.map((a, i) => (
                        <li key={i}>{formatVisit(a.valor)}</li>
                      ))}
                    </ul>
                  </div>
                ) : campos.visita_tecnica.valor ? (
                  formatVisit(campos.visita_tecnica.valor)
                ) : null}
                <DigestCitations citas={campos.visita_tecnica.citas} />
              </dd>
            </div>
          )}
        </dl>
      </div>

      {/* 4. Requisitos */}
      {requisitos && requisitos.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">Requisitos</h4>
          <ul aria-label="Requisitos" className="flex flex-col gap-2">
            {requisitos.map((req, index) => (
              <li
                key={index}
                className="rounded-md border border-warm-200/60 bg-warm-50/30 p-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="leading-relaxed text-slate-800">
                    {req.descripcion}
                  </span>
                  {req.obligatorio === true && (
                    <Badge tone="coral" className="shrink-0 text-[10px]">
                      Obligatorio
                    </Badge>
                  )}
                </div>
                <DigestCitations citas={req.citas} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. Ítems */}
      {items && items.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">Ítems solicitados</h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-slate-800">
            {items.map((it, index) => (
              <li key={index}>
                <span className="font-medium">{it.descripcion}</span>
                {it.cantidad != null && (
                  <span className="text-text-muted">
                    {" "}
                    (Cantidad: {it.cantidad} {it.unidad ?? ""})
                  </span>
                )}
                <DigestCitations citas={it.citas} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 6. Entregables */}
      {entregables && entregables.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">
            Entregables y plazos
          </h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-slate-800">
            {entregables.map((ent, index) => (
              <li key={index}>
                <span className="font-medium">{ent.descripcion}</span>
                {ent.plazo && (
                  <span className="text-text-muted"> [Plazo: {ent.plazo}]</span>
                )}
                <DigestCitations citas={ent.citas} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 7. Puntos a tener en cuenta */}
      {puntos_a_tener_en_cuenta && puntos_a_tener_en_cuenta.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">
            Puntos a tener en cuenta
          </h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-slate-800">
            {puntos_a_tener_en_cuenta.map((p, index) => (
              <li key={index}>
                <span>{p.descripcion}</span>
                <DigestCitations citas={p.citas} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 8. Resumen por anexo */}
      {resumenes && resumenes.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-slate-900 text-xs">Resumen por anexo</h4>
          <div className="flex flex-col gap-2">
            {resumenes.map((res, index) => (
              <div
                key={index}
                className="rounded-md border border-warm-200/60 bg-warm-50/40 p-2.5"
              >
                <span className="font-semibold text-slate-700">
                  {res.documento}
                </span>
                <p className="mt-1 text-slate-800 leading-relaxed">{res.texto}</p>
                <DigestCitations citas={res.citas} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 9. Fuentes y verificación */}
      {fuentes && fuentes.length > 0 && (
        <div className="border-t border-warm-200/80 pt-3">
          <h4 className="font-bold text-slate-700 text-[11px] uppercase tracking-wide">
            Fuentes analizadas
          </h4>
          <ul className="mt-1 flex flex-col gap-1 text-[11px] text-text-muted">
            {fuentes.map((f, index) => (
              <li key={index}>
                {f.texto_disponible
                  ? `${f.documento}: ${f.citas_verificadas} de ${f.citas_total} citas verificadas`
                  : `${f.documento}: sin texto para verificar las citas`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
