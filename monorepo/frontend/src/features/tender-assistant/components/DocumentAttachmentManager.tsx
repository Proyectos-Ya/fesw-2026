import React from "react";
import {
  FileText,
  FileSpreadsheet,
  FileImage,
  Trash2,
  AlertCircle,
} from "lucide-react";
import type { TenderChatDocument, SupportedDocumentType } from "../types";

export interface DocumentAttachmentManagerProps {
  documents: TenderChatDocument[];
  onDelete: (documentId: string) => Promise<unknown> | void;
  onNavigateToPanel?: () => void;
  onUpload?: (file: File) => Promise<unknown> | void;
  isUploading?: boolean;
  externalError?: string | null;
}

export function DocumentAttachmentManager({
  documents,
  onDelete,
  onNavigateToPanel,
  externalError = null,
}: DocumentAttachmentManagerProps) {
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (fileType: SupportedDocumentType) => {
    switch (fileType.toLowerCase()) {
      case "pdf":
        return <FileText className="h-4 w-4 text-red-500" />;
      case "xlsx":
        return <FileSpreadsheet className="h-4 w-4 text-emerald-600" />;
      case "png":
        return <FileImage className="h-4 w-4 text-blue-500" />;
      default:
        return <FileText className="h-4 w-4 text-text-muted" />;
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border-subtle bg-surface-inset p-3">
      {/* Banner de bases oficiales sincronizadas */}
      <div className="flex items-center justify-between rounded-lg bg-info-soft p-2.5 text-xs text-text-strong border border-info/30">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 shrink-0 text-info" />
          <span className="truncate font-medium">Bases y anexos oficiales sincronizados</span>
        </div>
        {onNavigateToPanel && (
          <button
            type="button"
            onClick={onNavigateToPanel}
            className="font-bold text-info-text hover:underline shrink-0 text-[0.6875rem]"
          >
            Ver panel
          </button>
        )}
      </div>

      {externalError && (
        <div className="flex items-center gap-1.5 rounded-md bg-danger-soft p-1.5 text-xs text-danger-text">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{externalError}</span>
        </div>
      )}

      {documents.length > 0 && (
        <div className="flex flex-col gap-1.5 pt-1">
          <span className="text-[0.6875rem] font-semibold text-text-muted">
            Archivos del chat ({documents.length})
          </span>
          <div className="flex flex-wrap gap-1.5">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-1.5 rounded-md border border-border-subtle bg-surface-card px-2 py-1 text-xs text-text-body shadow-xs"
              >
                {getFileIcon(doc.file_type)}
                <span className="max-w-[140px] truncate font-medium" title={doc.file_name}>
                  {doc.file_name}
                </span>
                <span className="rounded bg-surface-inset px-1 py-0.5 text-[0.625rem] font-medium text-text-body">
                  Chat antiguo
                </span>
                <span className="text-[0.625rem] text-text-muted">
                  {formatFileSize(doc.file_size_bytes)}
                </span>
                <button
                  type="button"
                  onClick={() => onDelete(doc.id)}
                  aria-label={`Eliminar documento ${doc.file_name}`}
                  className="ml-1 text-text-muted transition-colors hover:text-danger"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
