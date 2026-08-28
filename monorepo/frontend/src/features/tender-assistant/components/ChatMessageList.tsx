import React, { useEffect, useRef } from "react";
import { Bot, User as UserIcon, Quote, FileText, Loader2, AlertTriangle } from "lucide-react";
import type { TenderChatMessage } from "../types";

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


  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
      {messages.length === 0 && !isAsking && (
        <div className="flex flex-1 flex-col items-center justify-center p-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-50 text-blue-600 mb-3">
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
            className={`flex items-start gap-2.5 ${isUser ? "flex-row-reverse" : "flex-row"}`}
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
              className={`flex max-w-[85%] flex-col gap-1.5 rounded-2xl px-4 py-2.5 text-sm ${
                isUser
                  ? "bg-blue-600 text-white rounded-tr-none"
                  : "border border-slate-200 bg-white text-slate-800 shadow-xs rounded-tl-none"
              }`}
            >
              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {/* Render de citas textuales exactas */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 flex flex-col gap-1.5 border-t border-slate-100 pt-2">
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
                        <FileText className="h-3 w-3 text-red-500" />
                        <span>{c.document_name}</span>
                        {c.page_or_sheet && (
                          <span className="rounded bg-slate-200 px-1 py-0.2 text-[10px] text-slate-600 font-normal">
                            {c.page_or_sheet}
                          </span>
                        )}
                      </div>
                      <blockquote className="mt-1 italic text-slate-600 border-l-2 border-blue-400 pl-2">
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
        <div className="flex items-center gap-2 text-xs font-medium text-slate-500 bg-slate-50 p-2.5 rounded-xl border border-slate-200 w-fit">
          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" />
          <span>Analizando documentos y generando respuesta con citas...</span>
        </div>
      )}

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xl bg-amber-50 border border-amber-200 p-3 text-xs text-amber-900"
        >
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600" />
          <span>{error}</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
