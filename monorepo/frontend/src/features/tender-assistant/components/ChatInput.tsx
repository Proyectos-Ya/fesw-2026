import React, { useState, FormEvent, KeyboardEvent } from "react";
import { Send, AlertCircle, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (question: string) => Promise<unknown> | void;
  isAsking?: boolean;
  disabled?: boolean;
}


const MAX_CHARACTERS = 1000;

export function ChatInput({ onSend, isAsking = false, disabled = false }: ChatInputProps) {
  const [text, setText] = useState("");

  const charCount = text.length;
  const isOverLimit = charCount > MAX_CHARACTERS;
  const isSubmitDisabled = disabled || isAsking || isOverLimit || text.trim().length === 0;

  const handleSubmit = async (e?: FormEvent) => {
    if (e) e.preventDefault();
    if (isSubmitDisabled) return;

    const query = text.trim();
    setText("");
    await onSend(query);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSubmit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full border-t border-border-subtle bg-surface-card p-3">
      {isOverLimit && (
        <div
          role="alert"
          className="mb-2 flex items-center gap-2 rounded-lg bg-danger-soft p-2 text-xs font-medium text-danger-text"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-danger" />
          <span>La consulta supera los 1000 caracteres. Por favor, acorta tu pregunta.</span>
        </div>
      )}

      <div
        className={`relative flex flex-col rounded-xl border bg-surface-inset transition-colors focus-within:bg-surface-card ${
          isOverLimit
            ? "border-danger focus-within:ring-2 focus-within:ring-danger/20"
            : "border-border-default focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20"
        }`}
      >
        <textarea
          rows={2}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Haz una pregunta sobre esta licitación o sus bases adjuntas..."
          disabled={disabled || isAsking}
          className="w-full resize-none bg-transparent px-3.5 pt-3 pb-8 text-sm text-text-strong placeholder:text-text-muted focus:outline-none disabled:opacity-50"
        />

        <div className="absolute right-3 bottom-2.5 flex items-center gap-3">
          <span
            className={`text-xs font-medium transition-colors ${
              isOverLimit ? "font-semibold text-danger" : "text-text-muted"
            }`}
          >
            {charCount} / {MAX_CHARACTERS}
          </span>

          <button
            type="submit"
            disabled={isSubmitDisabled}
            aria-label={isAsking ? "Enviando..." : "Enviar pregunta"}
            className="flex min-h-8 py-1.5 items-center justify-center rounded-lg bg-blue-600 px-3 text-xs font-semibold text-white transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-border-default"
          >
            {isAsking ? (
              <>
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                <span>Enviando...</span>
              </>
            ) : (
              <>
                <Send className="mr-1.5 h-3.5 w-3.5" />
                <span>Enviar</span>
              </>
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
