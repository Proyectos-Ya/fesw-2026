'use client';

import { useState, useEffect, useCallback } from "react";
import type { MatchingResult } from "@/features/matches/tenderTypes";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "../services/savedTenders.service";

export function useSavedTenders() {
  const [savedMatches, setSavedMatches] = useState<MatchingResult[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const loadSaved = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchSavedTenders();
      setSavedMatches(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Error al cargar licitaciones guardadas";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSaved();
  }, [loadSaved]);

  const toggleSave = async (tenderId: string, isCurrentlySaved: boolean = true) => {
    const previousState = [...savedMatches];

    // Actualización optimista en memoria
    if (isCurrentlySaved) {
      setSavedMatches((prev) =>
        prev.filter((m) => (m.tender?.id ?? m.id) !== tenderId)
      );
    }

    try {
      if (isCurrentlySaved) {
        await unsaveTenderApi(tenderId);
      } else {
        await saveTenderApi(tenderId);
      }
    } catch {
      // Rollback en caso de error de red o servidor
      setSavedMatches(previousState);
      setToastMessage(
        isCurrentlySaved
          ? "No se pudo quitar la licitación. Inténtalo de nuevo."
          : "No se pudo guardar la licitación. Inténtalo de nuevo."
      );
    }
  };


  const clearToast = () => setToastMessage(null);

  return {
    savedTenders: savedMatches,
    loading,

    error,
    toastMessage,
    clearToast,
    toggleSave,
    reload: loadSaved,
  };
}