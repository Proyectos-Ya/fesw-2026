'use client';

import { useState, useEffect, useCallback } from "react";
import type { Tender } from "@/features/matches/tenderTypes";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "../services/savedTenders.service";

export function useSavedTenders() {
  const [savedTenders, setSavedTenders] = useState<Tender[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const loadSaved = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchSavedTenders();
      setSavedTenders(data.map((t) => ({ ...t, is_saved: true })));
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

  const toggleSave = async (tender: Tender) => {
    const isCurrentlySaved = tender.is_saved ?? true;
    const previousState = [...savedTenders];

    // Actualización optimista en memoria
    if (isCurrentlySaved) {
      setSavedTenders((prev) => prev.filter((item) => item.id !== tender.id));
    } else {
      setSavedTenders((prev) => [{ ...tender, is_saved: true }, ...prev]);
    }

    try {
      if (isCurrentlySaved) {
        await unsaveTenderApi(tender.id);
      } else {
        await saveTenderApi(tender.id);
      }
    } catch {
      // Rollback en caso de error de red o servidor
      setSavedTenders(previousState);
      setToastMessage(
        isCurrentlySaved
          ? "No se pudo quitar la licitación. Inténtalo de nuevo."
          : "No se pudo guardar la licitación. Inténtalo de nuevo."
      );
    }
  };

  const clearToast = () => setToastMessage(null);

  return {
    savedTenders,
    loading,
    error,
    toastMessage,
    clearToast,
    toggleSave,
    reload: loadSaved,
  };
}