"use client";

import { useId, useState } from "react";

import { Button } from "@/features/shared/components/Button";
import { Dialog } from "@/features/shared/components/Dialog";

interface DefaultTimeDialogProps {
  open: boolean;
  /** Cuántos de los hitos elegidos no tienen hora exacta. */
  count: number;
  onConfirm: (time: string) => void;
  onCancel: () => void;
}

const START_OF_WORKDAY = "09:00";

export function DefaultTimeDialog({ open, count, onConfirm, onCancel }: DefaultTimeDialogProps) {
  const [time, setTime] = useState(START_OF_WORKDAY);
  const inputId = useId();
  const valid = /^([01]\d|2[0-3]):[0-5]\d$/.test(time);

  return (
    <Dialog open={open} title="Confirma una hora para estos hitos" onClose={onCancel}>
      <p className="text-sm text-text-body">
        {count === 1 ? "1 hito no tiene hora exacta" : `${count} hitos no tienen hora exacta`} en las
        bases. Para no crear eventos incompletos, elige a qué hora (de Chile) agendarlos.
      </p>
      <form
        className="mt-4 space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) onConfirm(time);
        }}
      >
        <div className="space-y-1">
          <label htmlFor={inputId} className="text-xs font-semibold text-text-strong">
            Hora para los hitos sin hora exacta
          </label>
          <input
            id={inputId}
            type="time"
            value={time}
            onChange={(event) => setTime(event.target.value)}
            required
            className="block w-full rounded-md border border-border-default bg-surface-card px-3 py-2 font-mono text-sm text-text-strong"
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
          <Button type="submit" disabled={!valid}>
            Confirmar y sincronizar
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
