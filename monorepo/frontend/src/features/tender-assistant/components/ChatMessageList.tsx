import React, { useEffect, useRef } from "react";
import {
  Bot,
  User as UserIcon,
  Quote,
  FileText,
  FileSpreadsheet,
  FileImage,
  Loader2,
  AlertTriangle,
  AlertCircle,
} from "lucide-react";
import type { TenderChatMessage } from "../types";
import { DiscrepancyCard } from "./DiscrepancyCard";
import { UnbackedAspectsList } from "./UnbackedAspectsList";
import { InsufficientInfoBanner } from "./InsufficientInfoBanner";

interface ChatMessageListProps {
  messages: TenderChatMessage[];
  isAsking?: boolean;
  error?: string | null;
}

export function ChatMessageList({
  messages,
  isAsking = false,
  error = null,
}: ChatMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (bottomRef.current && typeof bottomRef.current.scrollIntoView === "function") {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isAsking]);

  const getDocumentIcon = (docName: string) => {
    const ext = docName.split(".").pop()?.toLowerCase();
    if (ext === "xlsx" || ext === "xls") {
      return <FileSpreadsheet className="h-3 w-3 text-emerald-600" />;
    }
    if (ext === "png" || ext === "jpg" || ext === "jpeg") {
      return <FileImage className="h-3 w-3 text-blue-500" />;
    }
    return <FileText className="h-3 w-3 text-red-500" />;
  };

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.length === 0 && !isAsking && (
        <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600">
            <Bot className="h-6 w-6" />
          </div>
          <h4 className="text-sm font-semibold text-slate-800">
            Asistente de Licitaciones
          </h4>
          <p className="mt-1 max-w-xs text-xs text-slate-500">
            Haz preguntas sobre las bases, requisitos técnicos, plazos de entrega o garantías de esta licitación.
          </p>
        </div>
      )}

      {messages.map((msg) => {
        const isUser = msg.role === "user";

        return (
          <div
            key={msg.id}
            className={`flex items-start gap-2.5 ${
              isUser ? "flex-row-reverse" : "flex-row"
            }`}
          >
            <div
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs ${
                isUser
                  ? "bg-blue-600 text-white"
                  : "bg-slate-200 text-slate-700"
              }`}
            >
              {isUser ? <UserIcon className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>

            <div
              className={`flex max-w-[85%] flex-col gap-2 rounded-2xl px-4 py-2.5 text-sm ${
                isUser
                  ? "rounded-tr-none bg-blue-600 text-white"
                  : "rounded-tl-none border border-slate-200 bg-white text-slate-800 shadow-xs"
              }`}
            >
              {/* Warnings de archivos dañados o corruptos (CA6) */}
              {msg.warnings && msg.warnings.length > 0 && (
                <div className="flex flex-col gap-1 rounded-lg border border-amber-200/80 bg-amber-50/90 p-2 text-xs text-amber-900 shadow-2xs">
                  {msg.warnings.map((w, wi) => (
                    <div key={wi} className="flex items-start gap-1.5">
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                      <span className="leading-snug">{w}</span>
                    </div>
                  ))}
                </div>
              )}

              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {/* Tarjetas de discrepancias detectadas (CA2) */}
              {msg.discrepancies && msg.discrepancies.length > 0 && (
                <div className="flex flex-col gap-2 pt-1">
                  {msg.discrepancies.map((discrepancy, di) => (
                    <DiscrepancyCard
                      key={`disc-${di}`}
                      discrepancy={discrepancy}
                    />
                  ))}
                </div>
              )}

              {/* Aspectos no especificados en los documentos (CA3) */}
              {msg.unbacked_aspects && msg.unbacked_aspects.length > 0 && (
                <UnbackedAspectsList aspects={msg.unbacked_aspects} />
              )}

              {/* Banner de información insuficiente / anti-alucinación (CA4) */}
              <InsufficientInfoBanner
                hasSufficientInfo={msg.has_sufficient_info}
              />

              {/* Citas textuales exactas por documento (CA1) */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-1 flex flex-col gap-1.5 border-t border-slate-100 pt-2">
                  <span className="flex items-center gap-1 text-[11px] font-semibold text-slate-500">
                    <Quote className="h-3 w-3 text-blue-500" />
                    Citas textuales de respaldo:
                  </span>

                  {msg.citations.map((c, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-slate-200/80 bg-slate-50/90 p-2 text-xs text-slate-700"
                    >
                      <div className="flex items-center gap-1 font-semibold text-slate-900 text-[11px]">
                        {getDocumentIcon(c.document_name)}
                        <span className="truncate" title={c.document_name}>
                          {c.document_name}
                        </span>
                        {c.page_or_sheet && (
                          <span className="shrink-0 rounded bg-slate-200 px-1 py-0.2 text-[10px] font-normal text-slate-600">
                            {c.page_or_sheet}
                          </span>
                        )}
                      </div>
                      <blockquote className="mt-1 border-l-2 border-blue-400 pl-2 italic text-slate-600">
                        &quot;{c.quote}&quot;
                      </blockquote>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {isAsking && (
        <div className="flex w-fit items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 p-2.5 text-xs font-medium text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
          <span>Analizando documentos y generando respuesta con citas...</span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>{error}</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
