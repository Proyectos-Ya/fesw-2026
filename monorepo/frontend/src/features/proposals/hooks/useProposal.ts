"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import {
  answerProposalQuestion,
  decideDiscrepancy,
  downloadTechnicalDocument,
  generateProposal,
  getProposal,
  regenerateProposal,
  resumeProposal,
  startFeasibility,
} from "../services/proposalService";
import type { DecisionAction, ProposalStage, ProposalView } from "../types";

export type ProposalState =
  | { kind: "loading" }
  | { kind: "not-started" }
  | { kind: "ready"; view: ProposalView }
  | { kind: "error"; message: string };

function mensajeDe(error: unknown): string {
  if (error instanceof ApiError || error instanceof TimeoutError) return error.message;
  return "Ocurrió un error inesperado. Intenta de nuevo.";
}

/**
 * Estado y acciones de la postulación de la empresa activa a una licitación.
 *
 * Después de cada acción se vuelve a leer el borrador completo: la vista trae
 * preguntas y origen de la cobertura que las respuestas de las acciones no
 * traen, y así la pantalla nunca muestra un estado a medias.
 */
export function useProposal(tenderId: string) {
  const [state, setState] = useState<ProposalState>({ kind: "loading" });
  const [stage, setStage] = useState<ProposalStage>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      const view = await getProposal(tenderId);
      setState({ kind: "ready", view });
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        setState({ kind: "not-started" });
        return;
      }
      setState({ kind: "error", message: mensajeDe(error) });
    }
  }, [tenderId]);

  useEffect(() => {
    // Carga inicial: el estado se actualiza cuando responde la API, no en el efecto.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  /** Ejecuta una acción, recarga y deja el error a la vista si falla. */
  const ejecutar = useCallback(
    async (accion: () => Promise<unknown>, etapa: ProposalStage = null) => {
      setActionError(null);
      setBusy(true);
      setStage(etapa);
      try {
        await accion();
        await reload();
      } catch (error) {
        setActionError(mensajeDe(error));
      } finally {
        setBusy(false);
        setStage(null);
      }
    },
    [reload],
  );

  const start = useCallback(
    () => ejecutar(() => startFeasibility(tenderId), "analyzing"),
    [ejecutar, tenderId],
  );
  const answer = useCallback(
    (questionId: string, label: string) =>
      ejecutar(() => answerProposalQuestion(tenderId, questionId, label)),
    [ejecutar, tenderId],
  );
  const decide = useCallback(
    (requirementId: string, action: DecisionAction) =>
      ejecutar(() => decideDiscrepancy(tenderId, requirementId, action)),
    [ejecutar, tenderId],
  );
  const resume = useCallback(
    () => ejecutar(() => resumeProposal(tenderId)),
    [ejecutar, tenderId],
  );
  const generate = useCallback(
    () => ejecutar(() => generateProposal(tenderId), "drafting"),
    [ejecutar, tenderId],
  );
  const regenerate = useCallback(
    (instructions: string) =>
      ejecutar(() => regenerateProposal(tenderId, instructions), "drafting"),
    [ejecutar, tenderId],
  );

  const download = useCallback(async () => {
    setActionError(null);
    try {
      const { blob, filename } = await downloadTechnicalDocument(tenderId);
      const url = URL.createObjectURL(blob);
      const enlace = document.createElement("a");
      enlace.href = url;
      enlace.download = filename;
      enlace.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setActionError(mensajeDe(error));
    }
  }, [tenderId]);

  return {
    state,
    stage,
    busy,
    actionError,
    clearActionError: () => setActionError(null),
    reload,
    start,
    answer,
    decide,
    resume,
    generate,
    regenerate,
    download,
  };
}
