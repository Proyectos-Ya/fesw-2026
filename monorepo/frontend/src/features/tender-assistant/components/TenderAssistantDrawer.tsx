import React from "react";
import { Sparkles, X, Plus, MessageSquarePlus, AlertTriangle, RefreshCw } from "lucide-react";

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
  /** Tras subir un documento: la ficha recarga los hitos que la IA extrae de él. */
  onDocumentsChanged?: () => void;
}

export function TenderAssistantDrawer({
  tenderId,
  tenderTitle,
  isOpen,
  onClose,
  onDocumentsChanged,
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
    error: documentError,
    removeDocument,
  } = useTenderDocuments(isOpen ? tenderId : "", onDocumentsChanged);

  return (
    <>
      {/* Backdrop */}
      <div
        data-testid="assistant-drawer-backdrop"
        aria-hidden="true"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-black/50 transition-opacity duration-300 ease-in-out ${
          isOpen ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />

      <aside
        aria-label="Asistente virtual de licitación"
        aria-hidden={!isOpen}
        className={`fixed inset-y-0 right-0 z-50 flex w-full max-w-lg transform flex-col border-l border-border-subtle bg-surface-card shadow-2xl transition-transform duration-300 ease-in-out ${
          isOpen ? "translate-x-0" : "pointer-events-none translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between gap-3 border-b border-border-subtle bg-surface-inset px-4 py-3">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary shadow-xs">
              <Sparkles className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h3 className="flex items-center gap-1.5 text-sm font-bold text-text-strong truncate">
                <span>Asistente Virtual IA</span>
              </h3>
              {tenderTitle && (
                <p className="text-xs text-text-muted truncate" title={tenderTitle}>
                  {tenderTitle}
                </p>
              )}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => void startNewChat()}
              disabled={isStartingNewChat || isAsking}
              aria-label="Nuevo Chat"
              title="Nuevo Chat"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border-subtle bg-surface-card text-text-muted shadow-2xs transition-colors hover:border-primary-border hover:bg-surface-hover hover:text-text-strong disabled:opacity-50 cursor-pointer"
            >
              <MessageSquarePlus className="h-4 w-4" />
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Cerrar asistente"
              title="Cerrar asistente"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-text-muted transition-colors hover:bg-surface-hover hover:text-text-strong cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Attachments Section */}
        <div className="p-3 border-b border-border-subtle bg-surface-card">
          <DocumentAttachmentManager
            documents={documents}
            onDelete={removeDocument}
            externalError={documentError}
          />
        </div>

        {/* History Error Banner */}
        {historyError && (
          <div
            role="alert"
            className="mx-4 mt-3 flex flex-col gap-2 rounded-xl border border-warning/40 bg-warning-soft p-3 text-xs text-text-strong shadow-2xs"
          >
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-warning mt-0.5" />
              <span className="font-medium leading-relaxed">{historyError}</span>
            </div>
            <div className="flex items-center gap-2 pl-6">
              <button
                type="button"
                onClick={() => void retryHistory()}
                className="flex items-center gap-1 rounded-md bg-primary px-2.5 py-1 font-semibold text-on-primary hover:bg-primary-hover transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
                <span>Reintentar</span>
              </button>
              <button
                type="button"
                onClick={() => void startNewChat()}
                className="flex items-center gap-1 rounded-md border border-warning/40 bg-surface-card px-2.5 py-1 font-semibold text-warning-text hover:bg-surface-hover transition-colors"
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
          tenderId={tenderId}
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
    </>
  );
}
