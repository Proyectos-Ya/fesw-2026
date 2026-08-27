import React from "react";
import { Sparkles, X } from "lucide-react";

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
    error: chatError,
    sendMessage,
  } = useTenderChat(isOpen ? tenderId : "");

  const {
    documents,
    isUploading,
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

        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar asistente"
          className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Attachments Section */}
      <div className="p-3 border-b border-slate-100 bg-white">
        <DocumentAttachmentManager
          documents={documents}
          onUpload={uploadDocument}
          onDelete={removeDocument}
          isUploading={isUploading}
        />
      </div>

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
      />
    </aside>
  );
}
