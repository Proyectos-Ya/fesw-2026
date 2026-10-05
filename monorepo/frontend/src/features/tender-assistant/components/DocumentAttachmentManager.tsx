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
        return <FileText className="h-4 w-4 text-slate-500" />;
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
      {/* Banner de bases oficiales sincronizadas */}
      <div className="flex items-center justify-between rounded-lg bg-blue-50/70 p-2.5 text-xs text-blue-900 border border-blue-200">
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="h-4 w-4 shrink-0 text-blue-600" />
          <span className="truncate font-medium">Bases y anexos oficiales sincronizados</span>
        </div>
        {onNavigateToPanel && (
          <button
            type="button"
            onClick={onNavigateToPanel}
            className="font-bold text-blue-700 hover:text-blue-900 hover:underline shrink-0 text-[11px]"
          >
            Ver panel
          </button>
        )}
      </div>

      {externalError && (
        <div className="flex items-center gap-1.5 rounded-md bg-red-50 p-1.5 text-xs text-red-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{externalError}</span>
        </div>
      )}

      {documents.length > 0 && (
        <div className="flex flex-col gap-1.5 pt-1">
          <span className="text-[11px] font-semibold text-slate-500">
            Archivos del chat ({documents.length})
          </span>
          <div className="flex flex-wrap gap-1.5">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="group flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 shadow-xs"
              >
                {getFileIcon(doc.file_type)}
                <span className="max-w-[140px] truncate font-medium" title={doc.file_name}>
                  {doc.file_name}
                </span>
                <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] font-medium text-slate-600">
                  Chat antiguo
                </span>
                <span className="text-[10px] text-slate-400">
                  {formatFileSize(doc.file_size_bytes)}
                </span>
                <button
                  type="button"
                  onClick={() => onDelete(doc.id)}
                  aria-label={`Eliminar documento ${doc.file_name}`}
                  className="ml-1 text-slate-400 transition-colors hover:text-red-600"
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
