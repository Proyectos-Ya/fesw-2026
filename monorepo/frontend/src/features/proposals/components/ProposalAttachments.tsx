"use client";

import { DocumentAttachmentManager } from "@/features/tender-assistant/components/DocumentAttachmentManager";
import type { useTenderDocuments } from "@/features/tender-assistant/hooks/useTenderDocuments";

interface ProposalAttachmentsProps {
  /**
   * Lo entrega `ProposalView`, que también usa la lista para saber si hay
   * archivos subidos después del análisis.
   */
  documentos: ReturnType<typeof useTenderDocuments>;
}

/**
 * Bases y anexos de la licitación. Son los mismos adjuntos del asistente: lo
 * que se sube acá también lo usa el chat, y viceversa.
 */
export function ProposalAttachments({ documentos }: ProposalAttachmentsProps) {
  const { documents, isUploading, error, uploadDocument, removeDocument } = documentos;
  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-4">
      <h3 className="mb-1 text-sm font-bold text-text-strong">Bases y anexos</h3>
      <p className="mb-3 text-xs text-text-muted">
        Si la Compra Ágil tiene bases o términos de referencia, súbelas: el análisis las usa
        como fuente principal y el borrador sale más preciso.
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
