"use client";

import Link from "next/link";
import { Icon } from "@/features/shared/components/Icon";
import { useCanWriteProposal } from "../hooks/useCanWriteProposal";
import { useProposal } from "../hooks/useProposal";
import { pendingRequirements } from "../utils/proposal";

interface ProposalEntryCardProps {
  tenderId: string;
  isClosed: boolean;
}

/** Entrada a la postulación desde la ficha de la licitación (HU-20). */
export function ProposalEntryCard({ tenderId, isClosed }: ProposalEntryCardProps) {
  const { state } = useProposal(tenderId);
  const canWrite = useCanWriteProposal();
  const href = `/matches/${tenderId}/postulacion`;

  if (state.kind === "loading" || state.kind === "error") return null;

  let titulo = "Generar postulación";
  let detalle = "Analizamos las bases con el perfil de tu empresa y redactamos el borrador.";
  let accion: string | null = canWrite && !isClosed ? "Generar postulación" : null;

  if (state.kind === "ready") {
    const view = state.view;
    if (view.status === "READY") {
      titulo = "Borrador de postulación listo";
      detalle = view.content?.technical_document
        ? "Revisa el borrador y descarga el documento técnico."
        : "Revisa el borrador y cópialo al formulario de la Compra Ágil.";
      accion = "Ver borrador";
    } else if (view.status === "PAUSED") {
      titulo = "Postulación en pausa";
      detalle = "Hay una exigencia excluyente que la empresa declaró no cumplir.";
      accion = "Revisar";
    } else if (view.status === "STOPPED") {
      titulo = "Postulación detenida";
      detalle = "Puedes reanudarla y corregir la respuesta que la detuvo.";
      accion = isClosed ? "Ver postulación" : "Reanudar";
    } else {
      const pendientes = pendingRequirements(view).length;
      titulo = "Postulación en curso";
      detalle =
        pendientes > 0
          ? `Quedan ${pendientes} pregunta${pendientes === 1 ? "" : "s"} por responder.`
          : "Ya puedes redactar el borrador.";
      accion = "Continuar postulación";
    }
  } else if (isClosed) {
    detalle = "Esta licitación se encuentra cerrada para postulaciones.";
  } else if (!canWrite) {
    detalle = "Solo quienes pueden generar postulaciones en esta empresa pueden iniciarla.";
  }

  return (
    <div className="mb-6 flex flex-col gap-4 rounded-lg border border-border-subtle bg-white p-6 shadow-xs sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-md bg-accent text-white shadow-sm">
          <Icon name="file-text" size={20} />
        </span>
        <div>
          <h3 className="mb-1 font-display text-lg font-bold text-text-strong">{titulo}</h3>
          <p className="mb-0 text-sm text-text-muted">{detalle}</p>
        </div>
      </div>
      {accion && (
        <Link
          href={href}
          className="inline-flex shrink-0 items-center justify-center gap-2 rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-white shadow-coral hover:bg-accent-hover"
        >
          {accion}
        </Link>
      )}
    </div>
  );
}
