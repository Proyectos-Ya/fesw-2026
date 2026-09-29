import { useCallback, useState } from "react";

import { setMilestoneReminder } from "../services/milestonesService";
import type { ReminderDaysBefore, TenderMilestone } from "../types";

type Overrides = Record<string, ReminderDaysBefore | null>;

/**
 * Recordatorios por hito (HU-16, criterio 10).
 *
 * El cambio se pinta antes de que el servidor conteste —elegir la anticipación
 * y ver el selector quieto medio segundo se siente roto— y se revierte al valor
 * que traía la tabla si el guardado falla.
 */
export function useMilestoneReminders(tenderId: string) {
  const [overrides, setOverrides] = useState<Overrides>({});
  const [error, setError] = useState<string | null>(null);

  const reminderOf = useCallback(
    (milestone: TenderMilestone): ReminderDaysBefore | null =>
      milestone.id in overrides ? overrides[milestone.id] : milestone.reminder_days_before,
    [overrides],
  );

  const change = useCallback(
    async (milestoneId: string, daysBefore: ReminderDaysBefore | null) => {
      setError(null);
      setOverrides((current) => ({ ...current, [milestoneId]: daysBefore }));
      try {
        const guardado = await setMilestoneReminder(tenderId, milestoneId, daysBefore);
        setOverrides((current) => ({
          ...current,
          [milestoneId]: guardado.reminder_days_before,
        }));
      } catch {
        setOverrides((current) => {
          const next = { ...current };
          delete next[milestoneId];
          return next;
        });
        setError("No se pudo guardar el recordatorio.");
      }
    },
    [tenderId],
  );

  return { reminderOf, change, error };
}
