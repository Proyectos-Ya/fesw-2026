"use client";

import { useCallback, useState } from "react";

import { Badge } from "@/features/shared/components/Badge";
import { Button } from "@/features/shared/components/Button";
import { Icon } from "@/features/shared/components/Icon";

import { useCalendarSync } from "../hooks/useCalendarSync";
import { useTenderMilestones } from "../hooks/useTenderMilestones";
import {
  MILESTONE_KIND_LABELS,
  MILESTONE_SOURCE_LABELS,
  type TenderMilestone,
} from "../types";
import { formatMilestoneDate, urgencyBadge } from "../utils/milestoneFormat";
import { CalendarSyncBar } from "./CalendarSyncBar";
import { DefaultTimeDialog } from "./DefaultTimeDialog";

interface MilestonesSectionProps {
  tenderId: string;
  /** Solo para pruebas: fija el "ahora" con que se calculan los plazos. */
  now?: Date;
}

const NO_MILESTONES: TenderMilestone[] = [];

export function MilestonesSection({ tenderId, now }: MilestonesSectionProps) {
  const { state, reload, refresh, extract, isExtracting, extractError, notice } =
    useTenderMilestones(tenderId);
  const milestones = state.status === "ready" ? state.data.milestones : NO_MILESTONES;
  const onSynced = useCallback(() => void refresh(), [refresh]);
  const calendar = useCalendarSync({ tenderId, milestones, onSynced });
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set());

  const toggle = (id: string) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const pending = milestones.filter((m) => m.urgency !== "vencido");
  const allPendingSelected = pending.length > 0 && pending.every((m) => selected.has(m.id));
  const toggleAll = () =>
    setSelected(allPendingSelected ? new Set() : new Set(pending.map((m) => m.id)));
  const selectable = calendar.available;

  if (state.status === "loading") {
    return (
      <p role="status" className="text-sm text-text-muted">
        Cargando hitos de la licitación…
      </p>
    );
  }

  if (state.status === "error") {
    return <ErrorAlert message={state.message} onRetry={reload} />;
  }

  const documentsCount = state.data.documents_count;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-text-muted">
          Plazos oficiales de Mercado Público y los que la IA encuentra en las bases.
        </p>
        <Button
          variant="ghost"
          onClick={() => void extract()}
          isLoading={isExtracting}
          disabled={documentsCount === 0 || isExtracting}
          className="shrink-0 border border-border-subtle"
        >
          <Icon name="sparkles" size={14} />
          {isExtracting ? "Analizando las bases…" : "Extraer hitos de las bases"}
        </Button>
      </div>

      {documentsCount === 0 && (
        <p className="rounded-md bg-surface-inset px-3 py-2 text-xs text-text-muted">
          Adjunta las bases en el asistente de la licitación para que la IA extraiga visitas
          técnicas, entregas y otros plazos.
        </p>
      )}

      {extractError && <ErrorAlert message={extractError} onRetry={() => void extract()} />}

      {notice && (
        <p role="status" className="text-xs text-text-muted">
          {notice}
        </p>
      )}

      {calendar.available && (
        <CalendarSyncBar
          calendar={calendar}
          selectedCount={selected.size}
          onSync={() => void calendar.sync(milestones.filter((m) => selected.has(m.id)).map((m) => m.id))}
        />
      )}

      {milestones.length === 0 ? (
        <p className="text-sm italic text-text-subtle">Esta licitación todavía no tiene hitos.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle text-[10px] font-bold uppercase tracking-caps text-text-subtle">
                {selectable && (
                  <th scope="col" className="w-8 py-2 pr-2">
                    <input
                      type="checkbox"
                      aria-label="Seleccionar todos los hitos pendientes"
                      checked={allPendingSelected}
                      onChange={toggleAll}
                      disabled={pending.length === 0}
                      className="size-4 accent-[var(--primary)]"
                    />
                  </th>
                )}
                <th scope="col" className="py-2 pr-4">Hito</th>
                <th scope="col" className="py-2 pr-4">Fecha</th>
                <th scope="col" className="py-2 pr-4">Plazo</th>
                <th scope="col" className="py-2">Calendario</th>
              </tr>
            </thead>
            <tbody>
              {milestones.map((milestone) => (
                <MilestoneRow
                  key={milestone.id}
                  milestone={milestone}
                  now={now}
                  selectable={selectable}
                  selected={selected.has(milestone.id)}
                  onToggle={() => toggle(milestone.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {calendar.state.status === "needsTime" && (
        <DefaultTimeDialog
          open
          count={calendar.state.missingCount}
          onConfirm={(time) => void calendar.confirmTime(time)}
          onCancel={calendar.cancelTime}
        />
      )}
    </div>
  );
}

interface MilestoneRowProps {
  milestone: TenderMilestone;
  now?: Date;
  selectable: boolean;
  selected: boolean;
  onToggle: () => void;
}

function MilestoneRow({ milestone, now, selectable, selected, onToggle }: MilestoneRowProps) {
  const urgency = urgencyBadge(milestone.urgency, milestone.due_at, now);
  const isPast = milestone.urgency === "vencido";

  return (
    <tr className={`border-b border-border-subtle align-top last:border-0 ${isPast ? "opacity-60" : ""}`}>
      {selectable && (
        <td className="py-3 pr-2">
          <input
            type="checkbox"
            aria-label={`Seleccionar ${milestone.title}`}
            checked={selected}
            onChange={onToggle}
            className="size-4 accent-[var(--primary)]"
          />
        </td>
      )}
      <td className="py-3 pr-4">
        <div className="font-semibold text-text-strong">{milestone.title}</div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <span className="text-xs text-text-muted">{MILESTONE_KIND_LABELS[milestone.kind]}</span>
          <Badge tone={milestone.source === "ia_documento" ? "info" : "neutral"}>
            {MILESTONE_SOURCE_LABELS[milestone.source]}
          </Badge>
        </div>
        {milestone.description && (
          <p className="mt-1 text-xs text-text-body">{milestone.description}</p>
        )}
        {milestone.source_excerpt && (
          <details className="mt-1 text-xs">
            <summary className="cursor-pointer text-primary">Ver párrafo de las bases</summary>
            <blockquote className="mt-1 border-l-2 border-border-subtle pl-2 italic text-text-muted">
              {milestone.source_excerpt}
            </blockquote>
          </details>
        )}
      </td>
      <td className="py-3 pr-4">
        <div className="font-mono text-text-strong">
          {formatMilestoneDate(milestone.due_at, milestone.has_time)}
        </div>
        {!milestone.has_time && (
          <div className="mt-0.5 text-xs text-text-subtle">Sin hora exacta</div>
        )}
      </td>
      <td className="py-3 pr-4">
        <Badge tone={urgency.tone} dot={urgency.tone !== "neutral"}>
          {urgency.label}
        </Badge>
      </td>
      <td className="py-3">
        {milestone.synced_providers.includes("google") ? (
          <Badge tone="teal" iconLeft={<Icon name="calendar-check" size={12} />}>
            En Google Calendar
          </Badge>
        ) : (
          <span className="text-xs text-text-subtle">—</span>
        )}
      </td>
    </tr>
  );
}

function ErrorAlert({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-md border border-danger/20 bg-danger-soft/30 px-4 py-3 text-sm font-medium text-danger sm:flex-row sm:items-center sm:justify-between"
    >
      <span>{message}</span>
      <Button variant="ghost" onClick={onRetry} className="shrink-0">
        Reintentar
      </Button>
    </div>
  );
}
