"use client";

import { useState } from "react";
import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";
import { Textarea } from "@/features/shared/components/Textarea";

const MAX = 1000;

interface RegenerateDialogProps {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onSubmit: (instructions: string) => void;
}

/** Instrucciones libres para volver a redactar el borrador (CA4). */
export function RegenerateDialog({ open, busy, onClose, onSubmit }: RegenerateDialogProps) {
  const [instrucciones, setInstrucciones] = useState("");
  const limpias = instrucciones.trim();
  return (
    <Dialog open={open} title="Regenerar borrador" onClose={onClose}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (!limpias || limpias.length > MAX) return;
          onSubmit(limpias);
        }}
      >
        <Textarea
          label="¿Qué quieres cambiar?"
          placeholder="Por ejemplo: usa un tono más formal, o da más énfasis a la experiencia en colegios."
          value={instrucciones}
          onChange={(event) => setInstrucciones(event.target.value)}
          charCount={instrucciones.length}
          maxChars={MAX}
        />
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={!limpias || limpias.length > MAX || busy}>
            Regenerar
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
