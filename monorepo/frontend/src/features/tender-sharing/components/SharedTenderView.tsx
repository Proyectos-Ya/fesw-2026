"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { formatCLP, formatDateTime } from "@/features/matches/utils/format";
import { compraAgilFichaUrl } from "@/features/matches/utils/links";
import { ApiError } from "@/features/shared/api/client";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";
import { MatchMeter } from "@/features/shared/components/MatchMeter";

import { getSharedTender } from "../services/sharingService";
import { SHARE_LINK_ERROR_CODES, type Recommendation, type SharedTender } from "../types";

type ViewState =
  | { status: "loading" }
  | { status: "ready"; data: SharedTender }
  | { status: "not_found" }
  | { status: "error" };

const RECOMMENDATION_TONE: Record<Recommendation, BadgeTone> = {
  Postular: "success",
  "Evaluar con cautela": "warning",
  "No recomendado": "danger",
};

/**
 * Lo que ve un tercero al abrir el enlace (HdU 19, criterio 2).
 *
 * Vive fuera del layout autenticado: no usa AuthProvider ni el selector de
 * empresa, porque quien lo abre no tiene cuenta.
 */
export function SharedTenderView({ token }: { token: string }) {
  const router = useRouter();
  const [state, setState] = useState<ViewState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getSharedTender(token)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 410) {
          // Criterios 6 y 7: a la página de "Enlace caducado", con el motivo.
          const motivo = SHARE_LINK_ERROR_CODES[error.code ?? ""] ?? "caducado";
          router.replace(`/enlace-caducado?motivo=${motivo}`);
          return;
        }
        setState({
          status: error instanceof ApiError && error.status === 404 ? "not_found" : "error",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [token, attempt, router]);

  if (state.status === "loading") {
    return (
      <p role="status" className="text-sm text-text-muted">
        Cargando la licitación compartida…
      </p>
    );
  }

  if (state.status === "not_found") {
    return (
      <div className="text-center">
        <h1 className="font-display text-2xl font-bold text-text-strong">Enlace no válido</h1>
        <p className="mt-2 text-sm text-text-muted">
          Revisa que la dirección esté completa, o pide a quien te lo envió un enlace nuevo.
        </p>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <div role="alert" className="flex flex-col items-center gap-3 text-center">
        <p className="text-sm text-text-body">No pudimos cargar la licitación en este momento.</p>
        <Button
          variant="ghost"
          onClick={() => {
            setState({ status: "loading" });
            setAttempt((n) => n + 1);
          }}
        >
          Reintentar
        </Button>
      </div>
    );
  }

  const t = state.data;
  return (
    <article className="space-y-8">
      <header>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone="teal">Compra Ágil</Badge>
          {t.is_closed && <Badge tone="neutral">Cerrada</Badge>}
          <span className="font-mono text-xs text-text-subtle">ID {t.code}</span>
        </div>
        <h1 className="font-display text-3xl font-bold leading-tight text-text-strong">{t.name}</h1>
        <p className="mt-2 text-sm text-text-muted">
          {t.buyer_name ?? "Organismo no informado"} · {t.buyer_unit}
          {t.region && ` · ${t.region}`}
        </p>
        <p className="mt-3 text-xs text-text-subtle">
          {t.supplier_name && <>Compartido por {t.supplier_name} · </>}
          Enlace válido hasta el {formatDateTime(t.expires_at)}
        </p>
      </header>

      <section className="grid grid-cols-1 gap-4 rounded-lg border border-border-subtle bg-surface-card p-5 sm:grid-cols-3">
        <Dato label="Monto disponible" value={formatCLP(t.available_amount_clp)} />
        <Dato label="Publicación" value={formatDateTime(t.published_at)} />
        <Dato label="Cierre" value={formatDateTime(t.closing_at)} />
      </section>

      <section aria-labelledby="shared-analysis" className="rounded-lg border border-primary/20 bg-teal-50/40 p-5">
        <h2 id="shared-analysis" className="mb-4 text-sm font-bold text-text-strong">
          Análisis de compatibilidad
        </h2>
        {t.analysis ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-4">
            <div className="flex flex-col items-center">
              <MatchMeter
                value={t.analysis.compatibility_score}
                size="md"
                thresholds={{ high: 70, mid: 40 }}
                colors={{ high: "var(--green-500)", mid: "var(--amber-500)", low: "var(--red-500)" }}
              />
            </div>
            <div className="flex flex-col gap-3 sm:col-span-3">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-muted">Recomendación:</span>
                <Badge tone={RECOMMENDATION_TONE[t.analysis.recommendation]}>
                  {t.analysis.recommendation}
                </Badge>
              </div>
              <div>
                <h3 className="mb-1 text-xs font-bold uppercase tracking-caps text-text-subtle">
                  Justificación
                </h3>
                <p className="whitespace-pre-line text-sm leading-relaxed text-text-body">
                  {t.analysis.justification}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-text-muted">
            Todavía no hay un análisis de compatibilidad para esta licitación.
          </p>
        )}
      </section>

      {t.description && (
        <section>
          <h2 className="mb-2 text-sm font-bold text-text-strong">Descripción</h2>
          <p className="whitespace-pre-line text-sm text-text-body">{t.description}</p>
        </section>
      )}

      {t.items.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-bold text-text-strong">Ítems solicitados</h2>
          <ul aria-label="Ítems solicitados" className="divide-y divide-border-subtle rounded-lg border border-border-subtle">
            {t.items.map((item, index) => (
              <li key={`${item.name}-${index}`} className="flex justify-between gap-4 px-4 py-2 text-sm">
                <span className="text-text-body">{item.name}</span>
                <span className="shrink-0 font-mono text-text-muted">
                  {item.quantity} {item.unit_of_measure}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <a
        href={compraAgilFichaUrl(t.code)}
        target="_blank"
        // Sin Referer: la URL de esta página lleva el token.
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary hover:underline"
      >
        <Icon name="external-link" size={14} />
        Ver la ficha oficial en Mercado Público
      </a>
    </article>
  );
}

function Dato({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] font-bold uppercase tracking-caps text-text-subtle">{label}</dt>
      <dd className="mt-1 text-sm font-semibold text-text-strong">{value}</dd>
    </div>
  );
}
