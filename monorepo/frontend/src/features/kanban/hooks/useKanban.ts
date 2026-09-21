"use client";

import { useCallback, useEffect, useState } from "react";
import { getTenderDetail } from "@/features/matches/services/tenderService";
import type { Tender } from "@/features/matches/tenderTypes";
import { ApiError } from "@/features/shared/api/client";
import type { KanbanCard, KanbanColumn } from "../kanbanTypes";
import * as kanbanService from "../services/kanban.service";

export function useKanban() {
  const [columns, setColumns] = useState<KanbanColumn[]>([]);
  const [cards, setCards] = useState<KanbanCard[]>([]);
  const [tenders, setTenders] = useState<Record<string, Tender>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [cols, cds] = await Promise.all([
        kanbanService.fetchColumns(),
        kanbanService.fetchCards(),
      ]);
      setColumns([...cols].sort((a, b) => a.position - b.position));
      setCards(cds);

      const details = await Promise.allSettled(
        cds.map((c) => getTenderDetail(c.tender_id)),
      );
      const tenderMap: Record<string, Tender> = {};
      cds.forEach((c, i) => {
        const result = details[i];
        if (result.status === "fulfilled") {
          tenderMap[c.tender_id] = result.value.tender;
        }
      });
      setTenders(tenderMap);
    } catch {
      setError("No se pudo cargar el tablero. Intenta de nuevo.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const addColumn = useCallback(
    async (name: string) => {
      const maxPos =
        columns.length > 0 ? Math.max(...columns.map((c) => c.position)) : -1;
      const col = await kanbanService.createColumn(name, maxPos + 1);
      setColumns((prev) =>
        [...prev, col].sort((a, b) => a.position - b.position),
      );
    },
    [columns],
  );

  const renameColumn = useCallback(
    async (id: string, name: string) => {
      const prev = columns.find((c) => c.id === id);
      if (!prev || prev.name === name) return;
      setColumns((cols) =>
        cols.map((c) => (c.id === id ? { ...c, name } : c)),
      );
      try {
        await kanbanService.updateColumn(id, { name });
      } catch {
        setColumns((cols) =>
          cols.map((c) => (c.id === id ? { ...c, name: prev.name } : c)),
        );
      }
    },
    [columns],
  );

  const deleteColumn = useCallback(
    async (id: string) => {
      const backupColumns = columns;
      const backupCards = cards;
      setColumns((cols) => cols.filter((c) => c.id !== id));
      setCards((cds) => cds.filter((c) => c.column_id !== id));
      try {
        await kanbanService.deleteColumn(id);
      } catch {
        setColumns(backupColumns);
        setCards(backupCards);
      }
    },
    [columns, cards],
  );

  const addCard = useCallback(
    async (tender_id: string, column_id: string, tender: Tender) => {
      try {
        const cardsInCol = cards.filter((c) => c.column_id === column_id);
        const card = await kanbanService.addCard(
          tender_id,
          column_id,
          cardsInCol.length,
        );
        setCards((prev) => [...prev, card]);
        setTenders((prev) => ({ ...prev, [tender_id]: tender }));
        setColumns((prev) =>
          prev.map((c) =>
            c.id === column_id
              ? { ...c, card_count: c.card_count + 1 }
              : c,
          ),
        );
      } catch (err) {
        if (err instanceof ApiError && err.status === 409) {
          throw err;
        }
        throw err;
      }
    },
    [cards],
  );

  const moveCard = useCallback(
    async (tender_id: string, column_id: string, position: number) => {
      const oldCard = cards.find((c) => c.tender_id === tender_id);
      if (!oldCard) return;

      setCards((prev) =>
        prev.map((c) =>
          c.tender_id === tender_id ? { ...c, column_id, position } : c,
        ),
      );
      if (oldCard.column_id !== column_id) {
        setColumns((prev) =>
          prev.map((c) => {
            if (c.id === oldCard.column_id)
              return { ...c, card_count: c.card_count - 1 };
            if (c.id === column_id)
              return { ...c, card_count: c.card_count + 1 };
            return c;
          }),
        );
      }

      try {
        await kanbanService.moveCard(tender_id, { column_id, position });
      } catch {
        setCards((prev) =>
          prev.map((c) => (c.tender_id === tender_id ? oldCard : c)),
        );
        if (oldCard.column_id !== column_id) {
          setColumns((prev) =>
            prev.map((c) => {
              if (c.id === oldCard.column_id)
                return { ...c, card_count: c.card_count + 1 };
              if (c.id === column_id)
                return { ...c, card_count: c.card_count - 1 };
              return c;
            }),
          );
        }
      }
    },
    [cards],
  );

  const removeCard = useCallback(
    async (tender_id: string) => {
      const card = cards.find((c) => c.tender_id === tender_id);
      if (!card) return;

      setCards((prev) => prev.filter((c) => c.tender_id !== tender_id));
      setColumns((prev) =>
        prev.map((c) =>
          c.id === card.column_id
            ? { ...c, card_count: c.card_count - 1 }
            : c,
        ),
      );

      try {
        await kanbanService.removeCard(tender_id);
      } catch {
        setCards((prev) => [...prev, card]);
        setColumns((prev) =>
          prev.map((c) =>
            c.id === card.column_id
              ? { ...c, card_count: c.card_count + 1 }
              : c,
          ),
        );
      }
    },
    [cards],
  );

  return {
    columns,
    cards,
    tenders,
    loading,
    error,
    addColumn,
    renameColumn,
    deleteColumn,
    addCard,
    moveCard,
    removeCard,
  };
}
