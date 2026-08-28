"use client";

import { useEffect, useState } from "react";
import { Badge, type BadgeTone } from "@/features/shared/components/Badge";
import { formatDateTime } from "@/features/matches/utils/format";
import type { DeliveryStatus, NotificationDelivery } from "../notificationTypes";
import { getDeliveries } from "../services/notificationService";

const ETIQUETA_ESTADO: Record<DeliveryStatus, { texto: string; tono: BadgeTone }> = {
  pending: { texto: "Pendiente", tono: "warning" },
  sent: { texto: "Enviado", tono: "success" },
  failed_permanent: { texto: "Fallido", tono: "danger" },
};

/**
 * Bandeja de salida de los correos de alerta.
 *
 * Hace visible lo que de otro modo solo existiría en la base: que un envío
 * quedó "Pendiente" porque el servicio de correo no respondió, cuántas veces se
 * reintentó y cuándo vuelve a intentarlo.
 */
export function DeliveryOutbox() {
  const [deliveries, setDeliveries] = useState<NotificationDelivery[] | null>(null);

  useEffect(() => {
    let cancelled = false;

    void (async () => {
      try {
        const items = await getDeliveries();
        if (!cancelled) setDeliveries(items);
      } catch {
        // La bandeja es informativa: si falla, se oculta en vez de romper la
        // página de preferencias.
        if (!cancelled) setDeliveries([]);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, []);

  if (deliveries === null || deliveries.length === 0) return null;

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-card p-6">
      <h2 className="text-sm font-semibold text-text-strong">Envíos de correo</h2>
      <p className="mt-1 text-xs text-text-subtle">
        Si el servicio de correo no responde, el aviso queda pendiente y se
        reintenta solo.
      </p>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead>
            <tr className="border-b border-border-subtle text-xs uppercase tracking-caps text-text-subtle">
              <th scope="col" className="py-2 pr-4 font-semibold">Tipo</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Estado</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Intentos</th>
              <th scope="col" className="py-2 pr-4 font-semibold">Detalle</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.map((delivery) => {
              const estado = ETIQUETA_ESTADO[delivery.status];
              return (
                <tr key={delivery.id} className="border-b border-border-subtle/60">
                  <td className="py-3 pr-4 text-text-body">
                    {delivery.kind === "digest" ? "Resumen diario" : "Inmediato"}
                    <div className="text-xs text-text-subtle">
                      {delivery.notification_ids.length}{" "}
                      {delivery.notification_ids.length === 1
                        ? "licitación"
                        : "licitaciones"}
                    </div>
                  </td>
                  <td className="py-3 pr-4">
                    <Badge tone={estado.tono}>{estado.texto}</Badge>
                  </td>
                  <td className="py-3 pr-4 font-mono text-text-body">
                    {delivery.attempts}
                  </td>
                  <td className="py-3 pr-4 text-xs text-text-subtle">
                    {delivery.status === "sent" && delivery.sent_at && (
                      <>Enviado el {formatDateTime(delivery.sent_at)}</>
                    )}
                    {delivery.status === "pending" && (
                      <>
                        Próximo intento: {formatDateTime(delivery.next_attempt_at)}
                        {delivery.last_error && (
                          <div className="mt-1 text-danger">{delivery.last_error}</div>
                        )}
                      </>
                    )}
                    {delivery.status === "failed_permanent" && (
                      <span className="text-danger">
                        {delivery.last_error ?? "No fue posible entregar el correo"}
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
