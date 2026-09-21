"use client";

import React from "react";
import { Button } from "@/features/shared/components/Button";

interface Props {
  cardCount: number;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteColumnDialog({ cardCount, onConfirm, onCancel }: Props) {
  return (
    <div className="mt-2 p-3 rounded-md bg-danger-soft border border-danger/20 text-sm">
      <p className="text-text-strong mb-3">
        Esta columna tiene{" "}
        <strong>
          {cardCount} licitación{cardCount !== 1 ? "es" : ""}
        </strong>
        . ¿Eliminar junto con las tarjetas?
      </p>
      <div className="flex gap-2">
        <Button variant="ghost" onClick={onCancel} type="button">
          Cancelar
        </Button>
        <button
          type="button"
          onClick={onConfirm}
          className="inline-flex items-center justify-center gap-2 rounded-md px-5 py-2.5 text-sm font-semibold transition-all duration-200 bg-danger text-white hover:opacity-90 active:scale-[0.98]"
        >
          Eliminar
        </button>
      </div>
    </div>
  );
}
