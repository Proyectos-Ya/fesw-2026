import { Icon } from "@/features/shared/components/Icon";

import type { ExpiredReason } from "../types";

const EXPLICACION: Record<ExpiredReason, string> = {
  caducado: "Los enlaces para compartir una licitación son válidos por 7 días, y este ya venció.",
  revocado: "Quien compartió esta licitación revocó el enlace, así que ya no está disponible.",
};

/** Página de "Enlace caducado" (HdU 19, criterios 6 y 7). */
export function ExpiredLinkNotice({ reason }: { reason: ExpiredReason | null }) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <span className="flex size-12 items-center justify-center rounded-full bg-warm-100 text-text-subtle">
        <Icon name="link-2-off" size={22} />
      </span>
      <h1 className="font-display text-2xl font-bold text-text-strong">Enlace caducado</h1>
      <p className="max-w-md text-sm text-text-body">{EXPLICACION[reason ?? "caducado"]}</p>
      <p className="max-w-md text-sm text-text-muted">
        Si todavía necesitas ver la licitación, pide un enlace nuevo a quien te la envió.
      </p>
    </div>
  );
}
