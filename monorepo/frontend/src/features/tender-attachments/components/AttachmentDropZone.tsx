"use client";

import { useRef } from "react";

import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

interface AttachmentDropZoneProps {
  /** Los archivos elegidos con el botón; los arrastrados los recibe el panel entero. */
  onFiles: (files: File[]) => void;
}

/**
 * Caja de "arrastra aquí" del panel de anexos. El soltar lo maneja la sección
 * completa; esta caja solo lo anuncia y ofrece el botón para elegir archivos.
 */
export function AttachmentDropZone({ onFiles }: AttachmentDropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div
      data-testid="attachments-drop-zone"
      className="flex flex-1 flex-col items-center gap-2 rounded-md border-2 border-dashed border-border-subtle px-4 py-4 text-center sm:flex-row sm:text-left"
    >
      <Icon name="upload" size={20} color="var(--primary)" />
      <p className="flex-1 text-sm text-text-muted">
        Arrastra aquí los anexos que descargaste de Mercado Público. Cada archivo se asigna a su
        anexo por el nombre.
      </p>
      <Button variant="ghost" type="button" onClick={() => inputRef.current?.click()}>
        Elegir archivos
      </Button>
      {/* Sin `accept`: el backend valida la extensión contra el anexo oficial. */}
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        aria-label="Elegir anexos para subir"
        data-testid="attachments-drop-input"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          event.target.value = "";
          if (files.length > 0) onFiles(files);
        }}
      />
    </div>
  );
}
