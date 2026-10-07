"use client";

import { useId, useState, type FormEvent } from "react";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Input } from "@/features/shared/components/Input";
import { Textarea } from "@/features/shared/components/Textarea";
import type { CapabilityEvidenceInput, CapabilityQuestion } from "../types";

/** Los mismos límites que valida el backend. */
const MAX_TEXTO = 255;
const MAX_DESCRIPCION = 2000;
const PRIMER_ANIO = 1900;

interface EvidenceFormProps {
  open: boolean;
  /** La pregunta `experiencia_proyecto` que el proyecto respalda. */
  question: CapabilityQuestion | null;
  onClose: () => void;
  /** Guarda el proyecto. Si rechaza, el error se muestra en el formulario. */
  onSubmit: (questionId: string, data: CapabilityEvidenceInput) => Promise<void>;
}

interface Errores {
  title?: string;
  buyer?: string;
  year?: string;
  amount?: string;
}

function mensajeDe(error: unknown): string {
  if (error instanceof ApiError && error.status === 409) {
    return 'La empresa no tiene respondido "Sí" a esta pregunta, así que no se puede agregar un proyecto. Cambia la respuesta y vuelve a intentarlo.';
  }
  if (error instanceof ApiError && error.status === 422) {
    return "Los datos del proyecto no son válidos. Revisa el año y el monto.";
  }
  if (error instanceof ApiError || error instanceof TimeoutError) return error.message;
  return "No se pudo guardar el proyecto. Intenta de nuevo.";
}

/** "12.000.000" o "12000000" a número; `null` si está vacío, `NaN` si no es un monto. */
function montoDe(texto: string): number | null {
  const limpio = texto.replace(/[.\s$]/g, "");
  if (limpio === "") return null;
  return /^\d+$/.test(limpio) ? Number(limpio) : Number.NaN;
}

function Campos({
  question,
  onClose,
  onSubmit,
}: {
  question: CapabilityQuestion;
  onClose: () => void;
  onSubmit: EvidenceFormProps["onSubmit"];
}) {
  const id = useId();
  const [title, setTitle] = useState("");
  const [buyer, setBuyer] = useState("");
  const [year, setYear] = useState("");
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const anioActual = new Date().getFullYear();

  const enviar = async (event: FormEvent) => {
    event.preventDefault();
    const anio = Number(year);
    const monto = montoDe(amount);
    const nuevos: Errores = {};
    if (title.trim() === "") nuevos.title = "Escribe el título del proyecto.";
    if (buyer.trim() === "") nuevos.buyer = "Escribe quién encargó el proyecto.";
    if (!Number.isInteger(anio) || anio < PRIMER_ANIO || anio > anioActual) {
      nuevos.year = `Indica un año entre ${PRIMER_ANIO} y ${anioActual}.`;
    }
    if (Number.isNaN(monto)) nuevos.amount = "Escribe el monto solo con números.";
    setErrores(nuevos);
    if (Object.keys(nuevos).length > 0) return;

    setErrorEnvio(null);
    setGuardando(true);
    try {
      await onSubmit(question.id, {
        title: title.trim(),
        buyer: buyer.trim(),
        year: anio,
        amount_clp: monto,
        description: description.trim() === "" ? null : description.trim(),
      });
      onClose();
    } catch (error) {
      setErrorEnvio(mensajeDe(error));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <form noValidate onSubmit={(e) => void enviar(e)} className="flex flex-col gap-3">
      <p className="text-sm text-text-muted">
        Respalda tu &quot;Sí&quot; a: <strong className="text-text-body">{question.question}</strong>{" "}
        La redacción podrá citarlo.
      </p>
      <Input
        id={`${id}-titulo`}
        label="Título del proyecto"
        value={title}
        maxLength={MAX_TEXTO}
        error={errores.title}
        onChange={(e) => setTitle(e.target.value)}
      />
      <Input
        id={`${id}-mandante`}
        label="Mandante"
        hint="Quién lo encargó, por ejemplo una municipalidad."
        value={buyer}
        maxLength={MAX_TEXTO}
        error={errores.buyer}
        onChange={(e) => setBuyer(e.target.value)}
      />
      <div className="grid gap-3 sm:grid-cols-2">
        <Input
          id={`${id}-anio`}
          label="Año"
          inputMode="numeric"
          value={year}
          error={errores.year}
          onChange={(e) => setYear(e.target.value)}
        />
        <Input
          id={`${id}-monto`}
          label="Monto en CLP"
          hint="Opcional."
          inputMode="numeric"
          value={amount}
          error={errores.amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </div>
      <Textarea
        id={`${id}-descripcion`}
        label="Descripción"
        hint="Opcional. Qué se hizo y su alcance."
        rows={3}
        value={description}
        maxLength={MAX_DESCRIPCION}
        charCount={description.length}
        maxChars={MAX_DESCRIPCION}
        onChange={(e) => setDescription(e.target.value)}
      />
      {errorEnvio && (
        <p role="alert" className="rounded-md bg-danger-soft px-3 py-2 text-xs text-red-700">
          {errorEnvio}
        </p>
      )}
      <div className="mt-1 flex justify-end gap-2">
        <Button type="button" variant="ghost" onClick={onClose}>
          Cancelar
        </Button>
        <Button type="submit" isLoading={guardando}>
          Guardar proyecto
        </Button>
      </div>
    </form>
  );
}

/**
 * Un proyecto que respalda un "Sí" de experiencia: título, mandante, año, monto
 * y descripción. No bloquea nada; se puede cerrar sin guardar.
 */
export function EvidenceForm({ open, question, onClose, onSubmit }: EvidenceFormProps) {
  return (
    <Dialog open={open && question !== null} title="Agregar proyecto" onClose={onClose}>
      {question && <Campos question={question} onClose={onClose} onSubmit={onSubmit} />}
    </Dialog>
  );
}
