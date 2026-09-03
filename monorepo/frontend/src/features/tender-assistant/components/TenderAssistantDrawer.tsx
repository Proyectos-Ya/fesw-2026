import React from "react";
import { Sparkles, X, Plus, AlertTriangle, RefreshCw } from "lucide-react";

import { useTenderChat } from "../hooks/useTenderChat";
import { useTenderDocuments } from "../hooks/useTenderDocuments";
import { DocumentAttachmentManager } from "./DocumentAttachmentManager";
import { ChatMessageList } from "./ChatMessageList";
import { ChatInput } from "./ChatInput";

interface TenderAssistantDrawerProps {
  tenderId: string;
  tenderTitle?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function TenderAssistantDrawer({
  tenderId,
  tenderTitle,
  isOpen,
  onClose,
}: TenderAssistantDrawerProps) {
  const {
    messages,
    isAsking,
    isStartingNewChat,
    error: chatError,
    historyError,
    startNewChat,
    retryHistory,
    sendMessage,
  } = useTenderChat(isOpen ? tenderId : "");

  const {
    documents,
    isUploading,
    error: documentError,
    uploadDocument,
    removeDocument,
  } = useTenderDocuments(isOpen ? tenderId : "");

  if (!isOpen) return null;

  return (
    <aside
      aria-label="Asistente virtual de licitación"
      className="fixed inset-y-0 right-0 z-50 flex w-full max-w-lg flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out border-l border-slate-200"
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/80 px-4 py-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-blue-600 text-white shadow-xs">
            <Sparkles className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h3 className="flex items-center gap-1.5 text-sm font-bold text-slate-900 truncate">
              <span>Asistente Virtual IA</span>
            </h3>
            {tenderTitle && (
              <p className="text-xs text-slate-500 truncate" title={tenderTitle}>
                {tenderTitle}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void startNewChat()}
            disabled={isStartingNewChat || isAsking}
            aria-label="Nuevo Chat"
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 shadow-2xs hover:border-blue-300 hover:bg-blue-50/50 hover:text-blue-600 transition-colors disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Nuevo Chat</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar asistente"
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Attachments Section */}
      <div className="p-3 border-b border-slate-100 bg-white">
        <DocumentAttachmentManager
          documents={documents}
          onUpload={uploadDocument}
          onDelete={removeDocument}
          isUploading={isUploading}
          externalError={documentError}
        />
      </div>

      {/* History Error Banner */}
      {historyError && (
        <div
          role="alert"
          className="mx-4 mt-3 flex flex-col gap-2 rounded-xl border border-amber-200 bg-amber-50/90 p-3 text-xs text-amber-900 shadow-2xs"
        >
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
            <span className="font-medium leading-relaxed">{historyError}</span>
          </div>
          <div className="flex items-center gap-2 pl-6">
            <button
              type="button"
              onClick={() => void retryHistory()}
              className="flex items-center gap-1 rounded-md bg-amber-600 px-2.5 py-1 font-semibold text-white hover:bg-amber-700 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Reintentar</span>
            </button>
            <button
              type="button"
              onClick={() => void startNewChat()}
              className="flex items-center gap-1 rounded-md border border-amber-300 bg-white px-2.5 py-1 font-semibold text-amber-800 hover:bg-amber-100/50 transition-colors"
            >
              <Plus className="h-3 w-3" />
              <span>Nuevo Chat</span>
            </button>
          </div>
        </div>
      )}

      {/* Chat Messages */}
      <ChatMessageList
        messages={messages}
        isAsking={isAsking}
        error={chatError}
      />

      {/* Input */}
      <ChatInput
        onSend={sendMessage}
        isAsking={isAsking}
        disabled={Boolean(historyError)}
      />
    </aside>
  );
}
