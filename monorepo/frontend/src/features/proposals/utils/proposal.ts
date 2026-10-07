import {
  KINDS_SIN_PREGUNTA,
  type CapabilityQuestion,
  type ProposalView,
  type Requirement,
} from "../types";

/** Exigencias que esperan la respuesta de la empresa. */
export function pendingRequirements(view: ProposalView): Requirement[] {
  return view.requirements.filter((r) => r.status === "desconocido");
}

function decisionDe(view: ProposalView, requirementId: string) {
  return [...view.discrepancy_decisions]
    .reverse()
    .find((d) => d.requirement_id === requirementId);
}

/**
 * ¿Se puede redactar? La misma regla que `ProposalDraft.can_generate` del
 * backend (la "pausa" del CA7), para no ofrecer un botón que dará 409.
 */
export function canGenerate(view: ProposalView): boolean {
  if (view.is_expired) return false;
  if (view.status !== "FEASIBILITY" && view.status !== "READY") return false;
  if (pendingRequirements(view).length > 0) return false;
  return !view.requirements.some(
    (r) =>
      r.mandatory &&
      r.status === "no_cumple" &&
      decisionDe(view, r.id)?.action !== "continue",
  );
}

export function questionFor(
  view: ProposalView,
  requirement: Requirement,
): CapabilityQuestion | null {
  if (!requirement.capability_question_id) return null;
  return view.questions.find((q) => q.id === requirement.capability_question_id) ?? null;
}

export function pausedRequirement(view: ProposalView): Requirement | null {
  if (view.status !== "PAUSED" || !view.paused_requirement_id) return null;
  return view.requirements.find((r) => r.id === view.paused_requirement_id) ?? null;
}

export interface PauseOrigin {
  answeredAt: string;
  fromAnotherTender: boolean;
}

/**
 * Si la pausa la causó una respuesta anterior de la empresa (no una de ahora),
 * cuándo y si fue en otra licitación. Sirve para que el aviso no sorprenda.
 */
export function pauseOrigin(view: ProposalView): PauseOrigin | null {
  const requirement = pausedRequirement(view);
  if (!requirement?.catalog_item_id) return null;
  const item = view.catalog_items.find((i) => i.id === requirement.catalog_item_id);
  if (!item?.answered_at) return null;
  return {
    answeredAt: item.answered_at,
    fromAnotherTender: item.tender_id !== null && item.tender_id !== view.tender_id,
  };
}

/**
 * Excluyentes que la empresa declaró no cumplir y que hay que responder de
 * nuevo para poder redactar. Es el caso de "Detener" y luego "Reanudar": la
 * exigencia queda en "No cumple" con la decisión `stop`, y sin esta lista no
 * habría forma de corregirla. Si se vuelve a responder "No", el backend borra
 * la decisión y pausa otra vez.
 *
 * Incluye también una excluyente en "No cumple" sin decisión: `canGenerate` la
 * bloquea igual, y así nunca queda un bloqueo sin salida. Las condiciones y los
 * documentos no se preguntan, así que no entran.
 */
export function requirementsToReanswer(view: ProposalView): Requirement[] {
  if (view.status !== "FEASIBILITY") return [];
  return view.requirements.filter(
    (r) =>
      r.mandatory &&
      KINDS_SIN_PREGUNTA.indexOf(r.kind) === -1 &&
      r.status === "no_cumple" &&
      decisionDe(view, r.id)?.action !== "continue",
  );
}

/** La excluyente que detuvo la postulación: la última decisión `stop`. */
function stoppedRequirement(view: ProposalView): Requirement | null {
  const detenidas = view.requirements.filter(
    (r) => r.mandatory && r.status === "no_cumple",
  );
  return (
    detenidas.find((r) => decisionDe(view, r.id)?.action === "stop") ?? detenidas[0] ?? null
  );
}

function conAdvertencia(view: ProposalView): boolean {
  return (
    view.warnings.length > 0 ||
    view.requirements.some(
      (r) =>
        r.mandatory &&
        r.status === "no_cumple" &&
        decisionDe(view, r.id)?.action === "continue",
    )
  );
}

/** Rojo: bloquea. Ámbar: hay que revisar algo. Verde azulado: informativo. */
export type StatusTone = "danger" | "warning" | "info";

/** La acción que ofrece el banner. Las demás están en su sección. */
export type StatusAction = "review" | "resume" | null;

export interface ProposalStatusInfo {
  tone: StatusTone;
  title: string;
  detail: string;
  action: StatusAction;
}

/** "la exigencia excluyente "X"", sin el punto final del texto de las bases. */
const laExigencia = (r: Requirement | null) =>
  r ? `la exigencia excluyente "${r.text.replace(/[.\s]+$/, "")}"` : "una exigencia excluyente";

/**
 * Qué pasa con la postulación y qué hacer, en una frase. Lo muestra
 * `ProposalStatusBanner`, y el texto vacío de la sección Borrador repite el
 * `detail`. `null` cuando no hay nada que decir: con el borrador listo y sin
 * advertencias, o vencida (ya lo dice el aviso de licitación cerrada).
 */
export function proposalStatus(view: ProposalView): ProposalStatusInfo | null {
  if (view.is_expired) return null;

  if (view.status === "PAUSED") {
    return {
      tone: "danger",
      title: "Postulación en pausa",
      detail: `La empresa declaró no cumplir ${laExigencia(pausedRequirement(view))}. Actualiza la respuesta, continúa con advertencia o detén la postulación. Las demás preguntas esperan hasta que decidas.`,
      action: "review",
    };
  }

  if (view.status === "STOPPED") {
    return {
      tone: "danger",
      title: "Postulación detenida",
      detail: `La detuviste porque la empresa no cumple ${laExigencia(stoppedRequirement(view))}. Si eso cambió, reanuda y responde de nuevo esa exigencia.`,
      action: "resume",
    };
  }

  const deNuevo = requirementsToReanswer(view);
  if (deNuevo.length > 0) {
    return {
      tone: "warning",
      title: "Responde de nuevo la exigencia que detuvo la postulación",
      detail: `Para redactar, responde otra vez ${laExigencia(deNuevo[0])} en la lista "Responder de nuevo". Si la respuesta sigue siendo "No", la postulación vuelve a quedar en pausa.`,
      action: null,
    };
  }

  const pendientes = pendingRequirements(view).length;
  if (pendientes > 0) {
    return {
      tone: "info",
      title: pendientes === 1 ? "Falta 1 respuesta" : `Faltan ${pendientes} respuestas`,
      detail: "Responde las preguntas del análisis y luego redacta el borrador.",
      action: null,
    };
  }

  const advertencia = conAdvertencia(view);
  if (view.status === "READY") {
    if (!advertencia) return null;
    return {
      tone: "warning",
      title: "Borrador listo, con advertencias",
      detail:
        "Decidiste continuar aunque la empresa no cumple una exigencia excluyente. Revisa las advertencias del borrador antes de enviar.",
      action: null,
    };
  }

  if (advertencia) {
    return {
      tone: "warning",
      title: "Lista para redactar, con advertencia",
      detail:
        'Decidiste continuar aunque la empresa no cumple una exigencia excluyente, y el borrador lo indicará. Usa "Redactar borrador" en el análisis.',
      action: null,
    };
  }
  return {
    tone: "info",
    title: "Lista para redactar",
    detail: 'Ya respondiste todo. Usa "Redactar borrador" en el análisis.',
    action: null,
  };
}

/**
 * Recomendación sobre las bases según con qué se analizó, en tono informativo.
 * `uploaded` son los nombres de los adjuntos que hay ahora en la licitación;
 * se comparan por nombre con `analysis_documents`. `null` si no hay nada que
 * decir o si el borrador es anterior a guardar ese dato.
 */
export function basesNotice(view: ProposalView, uploaded: string[]): string | null {
  const usados = view.analysis_documents;
  if (usados === null) return null;

  const nuevos = uploaded.filter((nombre) => !usados.some((d) => d.name === nombre));
  const ilegibles = usados.filter((d) => d.corrupted).map((d) => d.name);
  const frases: string[] = [];

  if (usados.length === 0) {
    const sujeto = view.content ? "Este borrador" : "Este análisis";
    if (nuevos.length > 0) {
      frases.push(`${sujeto} se hizo solo con la ficha.`);
    } else if (view.mentions_attachments) {
      frases.push(
        `${sujeto} se hizo solo con la ficha, pero la ficha menciona bases o anexos que no se subieron. Súbelos y vuelve a analizar.`,
      );
    } else {
      frases.push(
        `${sujeto} se hizo solo con la ficha. Si la Compra Ágil tiene bases, súbelas y vuelve a analizar.`,
      );
    }
  }
  if (ilegibles.length > 0) {
    frases.push(
      `No se pudo leer ${ilegibles.join(", ")}. Revisa el archivo y vuelve a analizar.`,
    );
  }
  if (nuevos.length > 0) {
    frases.push("Subiste archivos después del análisis. Vuelve a analizar para usarlos.");
  }
  return frases.length > 0 ? frases.join(" ") : null;
}
