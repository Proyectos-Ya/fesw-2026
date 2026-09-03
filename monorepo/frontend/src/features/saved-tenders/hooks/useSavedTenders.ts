'use client';

import { useState, useEffect, useCallback } from "react";
import type { MatchingResult, Tender } from "@/features/matches/tenderTypes";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "../services/savedTenders.service";
import { getSaveErrorMessage } from "../constants";

export interface UseSavedTendersOptions {
  autoFetch?: boolean;
}

export function useSavedTenders(options?: UseSavedTendersOptions) {
  const { autoFetch = true } = options ?? {};
  const [savedMatches, setSavedMatches] = useState<MatchingResult[]>([]);
  const [savedTenderIds, setSavedTenderIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState<boolean>(autoFetch);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const loadSaved = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchSavedTenders();
      setSavedMatches(data);
      setSavedTenderIds(new Set(data.map((m) => m.tender?.id ?? m.id)));
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : "Error al cargar licitaciones guardadas";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (autoFetch) {
      void loadSaved();
    }
  }, [autoFetch, loadSaved]);

  const toggleSave = async (
    tenderId: string,
    isCurrentlySaved?: boolean,
    tenderItem?: MatchingResult,
  ) => {
    const currentlySaved =
      isCurrentlySaved !== undefined
        ? isCurrentlySaved
        : savedTenderIds.has(tenderId) ||
          savedMatches.some((m) => (m.tender?.id ?? m.id) === tenderId);

    const previousMatches = [...savedMatches];
    const previousIds = new Set(savedTenderIds);

    setToastMessage(null);

    // Actualización optimista en memoria
    if (currentlySaved) {
      setSavedMatches((prev) =>
        prev.filter((m) => (m.tender?.id ?? m.id) !== tenderId),
      );
      setSavedTenderIds((prev) => {
        const next = new Set(prev);
        next.delete(tenderId);
        return next;
      });
    } else {
      const newItem: MatchingResult = tenderItem ?? {
        id: tenderId,
        supplier_id: "",
        tender_id: tenderId,
        similarity_score: 0,
        reranker_score: null,
        final_score: 0,
        model_version: "",
        calculated_at: new Date().toISOString(),
        tender: { id: tenderId } as unknown as Tender,
      };
      setSavedMatches((prev) => [newItem, ...prev]);
      setSavedTenderIds((prev) => {
        const next = new Set(prev);
        next.add(tenderId);
        return next;
      });
    }

    try {
      if (currentlySaved) {
        await unsaveTenderApi(tenderId);
      } else {
        await saveTenderApi(tenderId);
      }
    } catch {
      // Rollback en caso de error de red o servidor HTTP
      setSavedMatches(previousMatches);
      setSavedTenderIds(previousIds);
      setToastMessage(getSaveErrorMessage(currentlySaved));
    }
  };

  const clearToast = () => setToastMessage(null);

  const isSaved = useCallback(
    (id: string) => savedTenderIds.has(id),
    [savedTenderIds],
  );

  return {
    savedTenders: savedMatches,
    savedTenderIds,
    isSaved,
    loading,
    error,
    toastMessage,
    actionError: toastMessage,
    clearToast,
    toggleSave,
    reload: loadSaved,
  };
}