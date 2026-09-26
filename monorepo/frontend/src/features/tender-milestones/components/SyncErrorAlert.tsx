import { Button } from "@/features/shared/components/Button";

interface SyncErrorAlertProps {
  message: string;
  /** El acceso expiró o se revocó: reintentar no basta, hay que volver a autorizar. */
  reconnect: boolean;
  onRetry: () => void;
}

export function SyncErrorAlert({ message, reconnect, onRetry }: SyncErrorAlertProps) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-md border border-danger/20 bg-danger-soft/30 px-4 py-3 text-sm font-medium text-danger sm:flex-row sm:items-center sm:justify-between"
    >
      <span>{message}</span>
      <Button variant="ghost" onClick={onRetry} className="shrink-0">
        {reconnect ? "Reconectar Google Calendar" : "Reintentar"}
      </Button>
    </div>
  );
}
