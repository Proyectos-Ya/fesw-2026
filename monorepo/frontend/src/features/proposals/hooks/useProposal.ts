"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import {
  answerProposalQuestion,
  decideDiscrepancy,
  downloadTechnicalDocument,
  generateProposal,
  getProposal,
  reanalyzeProposal,
  regenerateProposal,
  requestTechnicalDocument,
  resumeProposal,
  startFeasibility,
  syncProposalAnswers,
} from "../services/proposalService";
import { addCapabilityEvidence } from "../services/capabilityService";
import type {
  CapabilityEvidenceInput,
  DecisionAction,
  PendingAnswer,
  ProposalStage,
  ProposalView,
} from "../types";

/** Confirmación breve para el `Toast`. El `id` cambia en cada una. */
export interface ProposalToast {
  id: number;
  message: string;
}

export type ProposalState =
  | { kind: "loading" }
  | { kind: "not-started" }
  | { kind: "ready"; view: ProposalView }
  | { kind: "error"; message: string };

function mensajeDe(error: unknown): string {
  if (error instanceof ApiError || error instanceof TimeoutError) return error.message;
  return "Ocurrió un error inesperado. Intenta de nuevo.";
}

const CONEXION_PERDIDA =
  "Se perdió la conexión con el servidor. Si la acción alcanzó a terminar, aparecerá al recargar la página.";

/**
 * ¿Pudo el backend terminar aunque el navegador no recibió la respuesta? Pasa
 * con un timeout del cliente, una red que se cae (`fetch` lanza `TypeError`) o
 * un 504 del proxy. Un error que responde el backend (409, 502...) es definitivo.
 */
function conexionPerdida(error: unknown): boolean {
  if (error instanceof TimeoutError || error instanceof TypeError) return true;
  return error instanceof ApiError && error.status === 504;
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
  const [notice, setNotice] = useState<string | null>(null);
  const [answering, setAnswering] = useState<PendingAnswer | null>(null);
  const [toast, setToast] = useState<ProposalToast | null>(null);
  // La pregunta de proyectos a la que se acaba de responder "Sí": se ofrece
  // agregar el proyecto que lo respalda.
  const [suggestedEvidence, setSuggestedEvidence] = useState<string | null>(null);
  const toastId = useRef(0);
  // La última versión leída, para saber si una acción que perdió la conexión
  // alcanzó a guardar algo en el backend.
  const ultimaVersion = useRef<string | null>(null);

  const confirmar = useCallback((message: string) => {
    toastId.current += 1;
    setToast({ id: toastId.current, message });
  }, []);
  const clearToast = useCallback(() => setToast(null), []);

  const reload = useCallback(async () => {
    try {
      const view = await getProposal(tenderId);
      ultimaVersion.current = view.updated_at;
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

  /**
   * Ejecuta una acción, recarga y deja el error a la vista si falla. Si se pasa
   * `confirmacion`, la muestra en un `Toast` cuando todo salió bien. Devuelve
   * si la acción terminó.
   */
  const ejecutar = useCallback(
    async (
      accion: () => Promise<unknown>,
      etapa: ProposalStage = null,
      confirmacion: string | null = null,
    ): Promise<boolean> => {
      setActionError(null);
      setNotice(null);
      setBusy(true);
      setStage(etapa);
      const antes = ultimaVersion.current;
      try {
        await accion();
        await reload();
        if (confirmacion) confirmar(confirmacion);
        return true;
      } catch (error) {
        if (!conexionPerdida(error)) {
          setActionError(mensajeDe(error));
          return false;
        }
        // El backend sigue trabajando aunque el navegador cortó: si el borrador
        // cambió, la acción terminó y se muestra como si nada. Así nadie
        // regenera de nuevo (y gasta otra llamada a Gemini) por un falso error.
        try {
          const view = await getProposal(tenderId);
          if (view.updated_at !== antes) {
            ultimaVersion.current = view.updated_at;
            setState({ kind: "ready", view });
            confirmar(confirmacion ?? "Listo. Se perdió la conexión, pero el cambio se guardó.");
            return true;
          }
        } catch {
          // Sin conexión todavía: queda el aviso de abajo.
        }
        setActionError(CONEXION_PERDIDA);
        return false;
      } finally {
        setBusy(false);
        setStage(null);
      }
    },
    [reload, confirmar, tenderId],
  );

  const start = useCallback(
    () => ejecutar(() => startFeasibility(tenderId), "analyzing"),
    [ejecutar, tenderId],
  );
  const reanalyze = useCallback(
    () =>
      ejecutar(async () => {
        const antes = state.kind === "ready" ? state.view.updated_at : null;
        const despues = await reanalyzeProposal(tenderId);
        if (antes !== null && despues.updated_at === antes) {
          setNotice(
            "No hubo cambios en las bases, el perfil ni la ficha desde el último análisis: el borrador se mantiene.",
          );
        }
      }, "analyzing"),
    [ejecutar, tenderId, state],
  );
  const answer = useCallback(
    async (questionId: string, label: string) => {
      // Para que solo el botón pulsado muestre que carga.
      setAnswering({ questionId, label });
      setSuggestedEvidence(null);
      const pregunta =
        state.kind === "ready"
          ? state.view.questions.find((q) => q.id === questionId)
          : undefined;
      const afirmaProyecto =
        pregunta?.kind === "experiencia_proyecto" &&
        pregunta.options.some((o) => o.label === label && o.polarity === "afirmativa");
      try {
        const guardada = await ejecutar(
          () => answerProposalQuestion(tenderId, questionId, label),
          null,
          "Respuesta guardada.",
        );
        if (guardada && afirmaProyecto) setSuggestedEvidence(questionId);
      } finally {
        setAnswering(null);
      }
    },
    [ejecutar, tenderId, state],
  );

  /**
   * Agrega un proyecto de experiencia. No pasa por `ejecutar`: los errores
   * (409, 422) los muestra el formulario, no el aviso de la página.
   */
  const addEvidence = useCallback(
    async (questionId: string, data: CapabilityEvidenceInput) => {
      await addCapabilityEvidence(questionId, data);
      setSuggestedEvidence(null);
      await reload();
      confirmar("Proyecto agregado. Se usará al redactar o regenerar.");
    },
    [reload, confirmar],
  );
  const dismissEvidence = useCallback(() => setSuggestedEvidence(null), []);
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
  const requestTechnical = useCallback(
    () => ejecutar(() => requestTechnicalDocument(tenderId), "drafting"),
    [ejecutar, tenderId],
  );
  const syncAnswers = useCallback(
    () =>
      ejecutar(
        () => syncProposalAnswers(tenderId),
        // Con texto redactado se vuelve a redactar: es la etapa que se ve.
        state.kind === "ready" && state.view.content ? "drafting" : null,
      ),
    [ejecutar, tenderId, state],
  );
  const regenerate = useCallback(
    (instructions: string) =>
      // La confirmación va en un Toast y no en `notice`: se va sola, y `notice`
      // queda para lo que hay que leer, como "No hubo cambios...".
      ejecutar(
        () => regenerateProposal(tenderId, instructions),
        "regenerating",
        "Borrador regenerado con tus instrucciones.",
      ),
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
      confirmar("Documento descargado.");
    } catch (error) {
      setActionError(mensajeDe(error));
    }
  }, [tenderId, confirmar]);

  return {
    state,
    stage,
    busy,
    answering,
    suggestedEvidence,
    dismissEvidence,
    addEvidence,
    toast,
    clearToast,
    actionError,
    clearActionError: () => setActionError(null),
    notice,
    clearNotice: () => setNotice(null),
    reanalyze,
    reload,
    start,
    answer,
    decide,
    resume,
    generate,
    regenerate,
    requestTechnical,
    syncAnswers,
    download,
  };
}
