import { Loader2 } from "lucide-react";
import { Badge } from "@/features/shared/components/Badge";
import type { AttachmentProcessingStatus } from "../types";

interface ProcessingBadgeProps {
  processing?: AttachmentProcessingStatus | null;
}

export function ProcessingBadge({ processing }: ProcessingBadgeProps) {
  if (!processing || processing === "unsupported") {
    return null;
  }

  if (processing === "processing") {
    return (
      <Badge
        tone="info"
        iconLeft={<Loader2 className="h-3 w-3 animate-spin" />}
      >
        Leyendo…
      </Badge>
    );
  }

  if (processing === "ready") {
    return <Badge tone="success">Resumen listo</Badge>;
  }

  if (processing === "failed") {
    return <Badge tone="danger">No se pudo leer</Badge>;
  }

  return null;
}
