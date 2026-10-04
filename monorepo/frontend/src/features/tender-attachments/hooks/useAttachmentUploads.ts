import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, TimeoutError } from "@/features/shared/api/client";

import { putToStorage, StorageUploadError } from "../services/storageUpload";
import {
  completeUpload,
  deleteAttachmentFile,
  requestUploadUrl,
} from "../services/tenderAttachmentsService";
import type { OfficialAttachment } from "../types";
import { normalizeAttachmentName } from "../utils/attachmentNames";
import { matchDroppedFiles, type RejectedFile } from "../utils/matchFiles";
import { InsecureContextError, sha256Hex } from "../utils/sha256";

export type UploadPhase =
  | "queued"
  | "hashing"
  | "requesting"
  | "uploading"
  | "verifying"
  | "deleting"
  | "error";

/** Lo que pasa localmente con una fila mientras se sube o se borra su archivo. */
export interface RowUpload {
  phase: UploadPhase;
  /** Fracción entre 0 y 1; solo cuenta en `uploading`. */
  progress: number;
  message: string | null;
  /** El archivo elegido, para poder reintentar sin pedirlo de nuevo. `null` si no sirve reintentar. */
  file: File | null;
}

interface UseAttachmentUploadsOptions {
  maxSizeBytes: number;
  /** Se llama cuando cambió lo que hay en el servidor: la lista hay que pedirla de nuevo. */
  onChanged: () => void;
}

const GENERIC_MESSAGE = "No se pudo subir el archivo. Inténtalo nuevamente.";

/** Mensaje para la persona; los errores con `code` del backend ya vienen redactados. */
function uploadErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code !== null) return error.message;
    if (error.status === 422) return "Los datos del archivo no son válidos.";
    return GENERIC_MESSAGE;
  }
  if (
    error instanceof StorageUploadError ||
    error instanceof TimeoutError ||
    error instanceof InsecureContextError
  ) {
    return error.message;
  }
  return GENERIC_MESSAGE;
}

/** Validaciones que no necesitan red; devuelve el motivo o `null` si el archivo sirve. */
function localProblem(
  attachment: OfficialAttachment,
  file: File,
  maxSizeBytes: number,
): string | null {
  if (file.size === 0) return "El archivo está vacío.";
  if (file.size > maxSizeBytes) {
    return `El archivo supera el máximo de ${Math.round(maxSizeBytes / 1048576)} MB.`;
  }
  if (normalizeAttachmentName(file.name) !== attachment.name_normalized) {
    return `«${file.name}» no corresponde a este anexo. Se esperaba «${attachment.name}».`;
  }
  return null;
}

/**
 * Subida de anexos fila por fila (plan 233, decisión 2).
 *
 * Flujo de un archivo: validar localmente → huella SHA-256 → pedir la URL →
 * PUT directo al almacenamiento → confirmar. Los archivos soltados se procesan
 * **en serie**: cada uno se lee entero en memoria para la huella (máximo 50 MB).
 * El backend vuelve a validar todo; esto solo ahorra viajes y da mensajes claros.
 */
export function useAttachmentUploads(
  tenderId: string,
  { maxSizeBytes, onChanged }: UseAttachmentUploadsOptions,
) {
  const [rows, setRows] = useState<Record<string, RowUpload>>({});
  const [rejections, setRejections] = useState<RejectedFile[]>([]);
  const busy = useRef(new Set<string>());
  const retryable = useRef(new Map<string, File>());
  const mounted = useRef(true);
  const onChangedRef = useRef(onChanged);

  useEffect(() => {
    onChangedRef.current = onChanged;
  }, [onChanged]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const setRow = useCallback((id: string, next: RowUpload | null) => {
    if (!mounted.current) return;
    setRows((current) => {
      if (next === null) {
        return Object.fromEntries(Object.entries(current).filter(([key]) => key !== id));
      }
      return { ...current, [id]: next };
    });
  }, []);

  const failRow = useCallback(
    (id: string, message: string, file: File | null) => {
      if (file) retryable.current.set(id, file);
      else retryable.current.delete(id);
      setRow(id, { phase: "error", progress: 0, message, file });
    },
    [setRow],
  );

  const uploadFile = useCallback(
    async (attachment: OfficialAttachment, file: File): Promise<boolean> => {
      const id = attachment.id;
      const problem = localProblem(attachment, file, maxSizeBytes);
      if (problem !== null) {
        // No se ofrece reintentar: el mismo archivo fallaría igual.
        failRow(id, problem, null);
        return false;
      }
      if (busy.current.has(id)) return false;
      busy.current.add(id);
      try {
        setRow(id, { phase: "hashing", progress: 0, message: null, file });
        const sha256 = await sha256Hex(file);
        setRow(id, { phase: "requesting", progress: 0, message: null, file });
        const response = await requestUploadUrl(tenderId, id, {
          file_name: file.name,
          size_bytes: file.size,
          mime: file.type,
          sha256,
        });
        if (!response.deduplicated) {
          setRow(id, { phase: "uploading", progress: 0, message: null, file });
          await putToStorage({
            url: response.url,
            method: response.method,
            headers: response.headers,
            body: file,
            onProgress: (progress) =>
              setRow(id, { phase: "uploading", progress, message: null, file }),
          });
          setRow(id, { phase: "verifying", progress: 1, message: null, file });
          await completeUpload(tenderId, response.upload_id);
        }
        retryable.current.delete(id);
        setRow(id, null);
        onChangedRef.current();
        return true;
      } catch (error) {
        failRow(id, uploadErrorMessage(error), file);
        // El servidor dejó el archivo rechazado: la lista ya no es la que se ve.
        if (error instanceof ApiError && error.code === "upload_verification_failed") {
          onChangedRef.current();
        }
        return false;
      } finally {
        busy.current.delete(id);
      }
    },
    [tenderId, maxSizeBytes, setRow, failRow],
  );

  const uploadDropped = useCallback(
    async (files: readonly File[], official: readonly OfficialAttachment[]): Promise<void> => {
      const { matched, rejected } = matchDroppedFiles(files, official);
      setRejections(rejected);
      for (const { attachment, file } of matched) {
        if (!busy.current.has(attachment.id)) {
          setRow(attachment.id, { phase: "queued", progress: 0, message: null, file });
        }
      }
      for (const { attachment, file } of matched) {
        await uploadFile(attachment, file);
      }
    },
    [setRow, uploadFile],
  );

  const retry = useCallback(
    async (attachment: OfficialAttachment): Promise<void> => {
      const file = retryable.current.get(attachment.id);
      if (file) await uploadFile(attachment, file);
    },
    [uploadFile],
  );

  const removeFile = useCallback(
    async (attachment: OfficialAttachment): Promise<void> => {
      const fileId = attachment.file?.id;
      if (!fileId || busy.current.has(attachment.id)) return;
      busy.current.add(attachment.id);
      try {
        setRow(attachment.id, { phase: "deleting", progress: 0, message: null, file: null });
        await deleteAttachmentFile(tenderId, fileId);
        setRow(attachment.id, null);
        onChangedRef.current();
      } catch (error) {
        failRow(attachment.id, uploadErrorMessage(error), null);
      } finally {
        busy.current.delete(attachment.id);
      }
    },
    [tenderId, setRow, failRow],
  );

  const dismissRejections = useCallback(() => setRejections([]), []);

  return { rows, rejections, uploadFile, uploadDropped, retry, removeFile, dismissRejections };
}
