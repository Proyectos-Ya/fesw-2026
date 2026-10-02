"use client";

import { DocumentAttachmentManager } from "@/features/tender-assistant/components/DocumentAttachmentManager";
import { useTenderDocuments } from "@/features/tender-assistant/hooks/useTenderDocuments";

/**
 * Bases y anexos de la licitación. Son los mismos adjuntos del asistente: lo
 * que se sube acá también lo usa el chat, y viceversa.
 */
export function ProposalAttachments({ tenderId }: { tenderId: string }) {
  const { documents, isUploading, error, uploadDocument, removeDocument } =
    useTenderDocuments(tenderId);
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-4">
      <h3 className="mb-1 text-sm font-bold text-text-strong">Bases y anexos</h3>
      <p className="mb-3 text-xs text-text-muted">
        Opcional. Si la ficha menciona bases o términos de referencia, súbelos para que
        el análisis y la redacción los consideren.
      </p>
      <DocumentAttachmentManager
        documents={documents}
        onUpload={uploadDocument}
        onDelete={removeDocument}
        isUploading={isUploading}
        externalError={error}
      />
    </div>
  );
}
