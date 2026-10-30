import { Icon } from "@/features/shared/components/Icon";
import type { Tender } from "../tenderTypes";
import { formatDeliveryAddress, formatDeliveryTerm } from "../utils/entrega";

interface DeliveryInfoProps {
  tender: Pick<Tender, "delivery_address" | "delivery_term_days">;
}

/**
 * Dirección y plazo de entrega del detalle (#294). Se muestra siempre: sin dato
 * dice que no está disponible, con los textos que pide HU-22 (#314).
 */
export function DeliveryInfo({ tender }: DeliveryInfoProps) {
  return (
    <section
      aria-label="Entrega"
      className="rounded-lg border border-border-subtle bg-surface-card p-4 shadow-xs"
    >
      <div className="mb-2 inline-flex items-center gap-1.5 text-[0.625rem] font-bold uppercase tracking-caps text-text-subtle">
        <Icon name="map-pin" size={12} color="var(--text-subtle)" />
        Entrega
      </div>
      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <dt className="text-xs text-text-muted">Dirección de entrega</dt>
          <dd className="text-sm font-semibold text-text-strong">
            {formatDeliveryAddress(tender.delivery_address)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted">Plazo de entrega</dt>
          <dd className="font-mono text-sm font-semibold text-text-strong">
            {formatDeliveryTerm(tender.delivery_term_days)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
