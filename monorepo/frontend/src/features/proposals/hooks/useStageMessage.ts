"use client";

import { useEffect, useState } from "react";
import type { ProposalStage } from "../types";

type Etapa = Exclude<ProposalStage, null>;

/**
 * Tres textos por etapa: al empezar, a los 10 s y a los 30 s.
 *
 * Son mensajes por tiempo, no etapas reales del backend: la llamada a Gemini
 * no informa avance, así que el texto cambia solo para que una espera larga no
 * parezca colgada. Las etapas reales quedan para una issue aparte con SSE
 * (`docs/plans/292-postulacion-preguntas-y-feedback.md` §2.6).
 */
const MENSAJES: Record<Etapa, readonly [string, string, string]> = {
  analyzing: [
    "Analizando bases y experiencia…",
    "Cruzando las bases con el perfil de tu empresa…",
    "Sigue analizando. Con bases largas puede tardar hasta dos minutos…",
  ],
  drafting: [
    "Redactando nombre, descripción y documentos…",
    "Escribiendo la descripción con la experiencia de tu empresa…",
    "Sigue redactando. Puede tardar hasta dos minutos…",
  ],
  regenerating: [
    "Regenerando el borrador con tus instrucciones…",
    "Aplicando tus instrucciones al nombre, la descripción y los documentos…",
    "Sigue regenerando. Puede tardar hasta dos minutos…",
  ],
};

const CAMBIOS_MS = [10_000, 30_000] as const;

/** El texto de la etapa en curso según cuánto lleva; `null` sin etapa. */
export function useStageMessage(stage: ProposalStage): string | null {
  // Se guarda con la etapa a la que pertenece: al cambiar de etapa el paso
  // viejo deja de valer sin tener que reiniciarlo dentro del efecto.
  const [avance, setAvance] = useState<{ stage: ProposalStage; paso: number }>({
    stage: null,
    paso: 0,
  });

  useEffect(() => {
    if (!stage) return;
    const temporizadores = CAMBIOS_MS.map((ms, i) =>
      setTimeout(() => setAvance({ stage, paso: i + 1 }), ms),
    );
    return () => temporizadores.forEach(clearTimeout);
  }, [stage]);

  if (!stage) return null;
  const paso = avance.stage === stage ? avance.paso : 0;
  return MENSAJES[stage][paso];
}
