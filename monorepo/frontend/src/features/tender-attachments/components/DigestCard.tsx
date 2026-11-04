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
  refreshKey?: string;
  className?: string;
}

export function DigestCard({ tenderId, refreshKey = "", className = "" }: DigestCardProps) {
  const { state, reload } = useTenderDigest(tenderId, refreshKey);

  if (state.status === "loading") {
    return (
      <div
        role="status"
        className={`flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-card p-4 text-xs text-text-muted shadow-xs ${className}`}
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
        className={`flex items-center justify-between rounded-lg border border-danger/30 bg-danger-soft p-4 text-xs text-danger-text ${className}`}
      >
        <div className="flex items-center gap-2">
          <AlertCircle className="h-4 w-4 shrink-0 text-danger" />
          <span>{state.message}</span>
        </div>
        <button
          type="button"
          onClick={reload}
          className="font-semibold text-danger-text hover:underline"
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
        className={`rounded-lg border border-border-subtle bg-surface-card p-4 text-xs text-text-muted shadow-xs ${className}`}
      >
        <h3 id="digest-heading" className="font-semibold text-text-strong">
          Resumen de los anexos
        </h3>
        <p className="mt-2">Todavía no hay anexos procesados para resumir.</p>
      </section>
    );
  }

  const digestData = digest.data ?? digest;
  const campos = digestData.campos ?? {
    presupuesto: null,
    fecha_publicacion: null,
    fecha_cierre_primer_llamado: null,
    fecha_cierre_segundo_llamado: null,
    visita_tecnica: null,
  };
  const {
    discrepancias = [],
    requisitos = [],
    items = [],
    entregables = [],
    puntos_a_tener_en_cuenta = [],
    resumenes = [],
    fuentes = [],
  } = digestData;

  return (
    <section
      aria-labelledby="digest-heading"
      className={`flex flex-col gap-4 rounded-xl border border-border-subtle bg-surface-card p-5 text-xs text-text-body shadow-xs ${className}`}
    >
      {/* 1. Encabezado y aviso de IA */}
      <div className="flex flex-col gap-1.5 border-b border-border-subtle pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="digest-heading" className="text-sm font-bold text-text-strong">
            Resumen de los anexos
          </h3>
          <Badge tone="info" iconLeft={<Bot className="h-3 w-3" />}>
            Generado con IA
          </Badge>
        </div>
        <p className="text-[0.6875rem] text-text-muted leading-relaxed">{AI_NOTICE}</p>
        {digest.scope === "workspace" && (
          <p className="text-[0.6875rem] font-medium text-warning-text">
            Incluye anexos que solo ve tu empresa.
          </p>
        )}
        {digest.pending_sources > 0 && (
          <p className="text-[0.6875rem] text-info-text">
            Todavía estamos leyendo {digest.pending_sources} anexo(s).
          </p>
        )}
      </div>

      {/* 2. Discrepancias primero */}
      {discrepancias && discrepancias.length > 0 && (
        <div className="flex flex-col gap-2">
          <h4 className="font-bold text-text-strong text-xs">
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
        <h4 className="font-bold text-text-strong text-xs">Fechas y presupuesto</h4>
        <dl className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
          {campos.presupuesto && (
            <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
              <dt className="font-semibold text-text-body">Presupuesto</dt>
              <dd className="mt-0.5 text-text-strong">
                {campos.presupuesto.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-warning-text">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[0.6875rem]">
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
            <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
              <dt className="font-semibold text-text-body">Publicación</dt>
              <dd className="mt-0.5 text-text-strong">
                {campos.fecha_publicacion.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-warning-text">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[0.6875rem]">
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
            <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
              <dt className="font-semibold text-text-body">
                Cierre del primer llamado
              </dt>
              <dd className="mt-0.5 text-text-strong">
                {campos.fecha_cierre_primer_llamado.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-warning-text">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[0.6875rem]">
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
            <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5">
              <dt className="font-semibold text-text-body">
                Cierre del segundo llamado
              </dt>
              <dd className="mt-0.5 text-text-strong">
                {campos.fecha_cierre_segundo_llamado.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-warning-text">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[0.6875rem]">
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
            <div className="rounded-md border border-border-subtle bg-surface-inset p-2.5 sm:col-span-2">
              <dt className="font-semibold text-text-body">Visita técnica</dt>
              <dd className="mt-0.5 text-text-strong">
                {campos.visita_tecnica.en_conflicto ? (
                  <div>
                    <span className="font-semibold text-warning-text">
                      Los anexos no coinciden
                    </span>
                    <ul className="mt-1 list-disc pl-4 text-[0.6875rem]">
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
          <h4 className="font-bold text-text-strong text-xs">Requisitos</h4>
          <ul aria-label="Requisitos" className="flex flex-col gap-2">
            {requisitos.map((req, index) => (
              <li
                key={index}
                className="rounded-md border border-border-subtle bg-surface-inset p-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <span className="leading-relaxed text-text-body">
                    {req.descripcion}
                  </span>
                  {req.obligatorio === true && (
                    <Badge tone="coral" className="shrink-0 text-[0.625rem]">
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
          <h4 className="font-bold text-text-strong text-xs">Ítems solicitados</h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-text-body">
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
          <h4 className="font-bold text-text-strong text-xs">
            Entregables y plazos
          </h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-text-body">
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
          <h4 className="font-bold text-text-strong text-xs">
            Puntos a tener en cuenta
          </h4>
          <ul className="flex flex-col gap-1.5 list-disc pl-4 text-text-body">
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
          <h4 className="font-bold text-text-strong text-xs">Resumen por anexo</h4>
          <div className="flex flex-col gap-2">
            {resumenes.map((res, index) => (
              <div
                key={index}
                className="rounded-md border border-border-subtle bg-surface-inset p-2.5"
              >
                <span className="font-semibold text-text-body">
                  {res.documento}
                </span>
                <p className="mt-1 text-text-body leading-relaxed">{res.texto}</p>
                <DigestCitations citas={res.citas} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 9. Fuentes y verificación */}
      {fuentes && fuentes.length > 0 && (
        <div className="border-t border-border-subtle pt-3">
          <h4 className="font-bold text-text-body text-[0.6875rem] uppercase tracking-wide">
            Fuentes analizadas
          </h4>
          <ul className="mt-1 flex flex-col gap-1 text-[0.6875rem] text-text-muted">
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
