"use client";

import { useRef, useState, type DragEvent } from "react";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

interface AttachmentDropZoneProps {
  onFiles: (files: File[]) => void;
  disabled?: boolean;
}

/**
 * Caja de "arrastra aquí" del panel de anexos. Permite soltar archivos o elegirlos con el botón.
 */
export function AttachmentDropZone({ onFiles, disabled = false }: AttachmentDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    if (disabled) return;
    event.preventDefault();
    event.stopPropagation();
    event.dataTransfer.dropEffect = "copy";
    setIsDragOver(true);
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);
    if (disabled) return;
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) onFiles(files);
  }

  return (
    <div
      data-testid="attachments-drop-zone"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={`flex flex-1 flex-col items-center gap-2 rounded-md border-2 border-dashed px-4 py-4 text-center transition-colors sm:flex-row sm:text-left ${
        isDragOver
          ? "border-primary bg-primary/10 ring-2 ring-primary ring-inset"
          : "border-border-subtle"
      } ${disabled ? "opacity-60 pointer-events-none" : ""}`}
    >
      <Icon name="upload" size={20} color="var(--primary)" />
      <p className="flex-1 text-sm text-text-muted">
        Arrastra aquí los anexos que descargaste de Mercado Público o suelta un archivo directamente
        sobre su fila correspondiente.
      </p>
      <Button
        variant="ghost"
        type="button"
        disabled={disabled}
        onClick={() => !disabled && inputRef.current?.click()}
      >
        Elegir archivos
      </Button>
      {/* Sin `accept`: el backend valida la extensión contra el anexo oficial. */}
      <input
        ref={inputRef}
        type="file"
        multiple
        disabled={disabled}
        className="hidden"
        aria-label="Elegir anexos para subir"
        data-testid="attachments-drop-input"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0 && !disabled) onFiles(files);
        }}
      />
    </div>
  );
}
