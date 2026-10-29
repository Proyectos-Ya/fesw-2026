import { Badge } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import type { ReviewStatus } from "../hooks/useProfileWizard";

/** Estado de revisión de un campo y las acciones que el usuario puede hacer sobre él. */
export interface FieldReview {
  /** `undefined`: el campo no viene de una importación y no se revisa. */
  status: ReviewStatus | undefined;
  onConfirm: () => void;
  onEdit: () => void;
  onClear: () => void;
}

interface ImportedFieldReviewProps extends FieldReview {
  /** Nombre del campo en minúsculas, para el nombre accesible de los botones. */
  fieldLabel: string;
}

/** Un campo importado solo se escribe a mano mientras se edita. */
export function isFieldLocked(status: ReviewStatus | undefined): boolean {
  return status === "pending" || status === "confirmed";
}

/** Insignia de revisión y acciones de un campo precargado desde el RUT. */
export function ImportedFieldReview({
  fieldLabel,
  status,
  onConfirm,
  onEdit,
  onClear,
}: ImportedFieldReviewProps) {
  if (!status) return null;
  const isConfirmed = status === "confirmed";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge tone={isConfirmed ? "success" : "warning"} dot>
        {isConfirmed ? "Revisado" : "Pendiente de revisión"}
      </Badge>
      {!isConfirmed && (
        <Button
          type="button"
          variant="primary"
          className="px-3 py-1.5 text-xs"
          aria-label={`Confirmar ${fieldLabel}`}
          onClick={onConfirm}
        >
          Confirmar
        </Button>
      )}
      {status !== "editing" && (
        <Button
          type="button"
          variant="ghost"
          className="px-3 py-1.5 text-xs"
          aria-label={`Editar ${fieldLabel}`}
          onClick={onEdit}
        >
          Editar
        </Button>
      )}
      <Button
        type="button"
        variant="ghost"
        className="px-3 py-1.5 text-xs"
        aria-label={`Borrar ${fieldLabel}`}
        onClick={onClear}
      >
        Borrar
      </Button>
    </div>
  );
}
