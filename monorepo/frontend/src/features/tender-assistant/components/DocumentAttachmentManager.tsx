import React, { useRef, useState, ChangeEvent } from "react";
import {
  FileText,
  FileSpreadsheet,
  FileImage,
  Upload,
  Trash2,
  Loader2,
  AlertCircle,
} from "lucide-react";
import type { TenderChatDocument, SupportedDocumentType } from "../types";
import { MAX_ATTACHED_DOCUMENTS } from "../types";

interface DocumentAttachmentManagerProps {
  documents: TenderChatDocument[];
  onUpload: (file: File) => Promise<unknown> | void;
  onDelete: (documentId: string) => Promise<unknown> | void;
  isUploading?: boolean;
  externalError?: string | null;
}

const ALLOWED_EXTENSIONS = [".pdf", ".xlsx", ".png"];
const MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024; // 20MB

export function DocumentAttachmentManager({
  documents,
  onUpload,
  onDelete,
  isUploading = false,
  externalError = null,
}: DocumentAttachmentManagerProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  const displayError = localError || externalError;
  const isLimitReached = documents.length >= MAX_ATTACHED_DOCUMENTS;

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

  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    setLocalError(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Reset input value to allow re-selecting same file
    if (fileInputRef.current) fileInputRef.current.value = "";

    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setLocalError("Solo se permiten archivos PDF, Excel (.xlsx) e imágenes PNG.");
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setLocalError("El archivo supera el límite máximo de 20 MB.");
      return;
    }

    if (isLimitReached) {
      setLocalError(
        `Se ha alcanzado el límite máximo de ${MAX_ATTACHED_DOCUMENTS} documentos por licitación.`
      );
      return;
    }

    try {
      await onUpload(file);
    } catch {
      // Error handled by parent hook / service
    }
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-700">
          Documentos adjuntos ({documents.length}/{MAX_ATTACHED_DOCUMENTS})
        </span>

        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading || isLimitReached}
          title={
            isLimitReached
              ? `Límite máximo de ${MAX_ATTACHED_DOCUMENTS} documentos alcanzado`
              : "Adjuntar documento"
          }
          className="flex items-center gap-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 shadow-xs transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isUploading ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
              <span>Subiendo...</span>
            </>
          ) : (
            <>
              <Upload className="h-3.5 w-3.5 text-blue-600" />
              <span>
                {isLimitReached
                  ? "Límite alcanzado"
                  : "Adjuntar (.pdf, .xlsx, .png)"}
              </span>
            </>
          )}
        </button>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.xlsx,.png"
          data-testid="file-upload-input"
          onChange={handleFileChange}
          className="hidden"
        />
      </div>

      {displayError && (
        <div className="flex items-center gap-1.5 rounded-md bg-red-50 p-1.5 text-xs text-red-600">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{displayError}</span>
        </div>
      )}

      {documents.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-1">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="group flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 shadow-xs"
            >
              {getFileIcon(doc.file_type)}
              <span className="max-w-[140px] truncate font-medium" title={doc.file_name}>
                {doc.file_name}
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
      )}
    </div>
  );
}
