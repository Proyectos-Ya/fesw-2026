"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { ApiError, TimeoutError } from "@/features/shared/api/client";
import {
  fetchSavedTenders,
  saveTenderApi,
  unsaveTenderApi,
} from "@/features/saved-tenders/services/savedTenders.service";
import { searchTenders } from "../services/searchService";
import type { Tender } from "@/features/matches/tenderTypes";
import type { TenderSearchParams } from "../types";
import {
  type AvailabilityFilter,
  DEBOUNCE_MS,
  PAGE_SIZE,
} from "../data/searchConstants";

export const SEARCH_STORAGE_KEY = "proyectosya_last_search";

export interface SearchState {
  items: Tender[];
  total: number;
  isTruncated: boolean;
  isLoading: boolean;
  error: string | null;
  isServiceUnavailable: boolean;
}

export function useTenderSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // 1. Restore search state from sessionStorage if URL query is empty on mount
  useEffect(() => {
    if (typeof window === "undefined") return;
    const currentQuery = searchParams.toString();
    if (!currentQuery) {
      try {
        const savedQuery = window.sessionStorage.getItem(SEARCH_STORAGE_KEY);
        if (savedQuery) {
          router.replace(`${pathname}?${savedQuery}`, { scroll: false });
        }
      } catch (err) {
        console.error("Error al restaurar búsqueda desde sessionStorage:", err);
      }
    }
  }, [pathname, router, searchParams]);

  // 2. Parse params from URL
  const urlQuery = searchParams.get("q") ?? "";
  const urlRegions = useMemo(() => searchParams.getAll("regions"), [searchParams]);
  const rawAvailability = searchParams.get("availability");
  const urlAvailability: AvailabilityFilter =
    rawAvailability === "vigentes" || rawAvailability === "cerradas"
      ? rawAvailability
      : null;

  const urlMinAmount = searchParams.get("min_amount")
    ? Number(searchParams.get("min_amount"))
    : undefined;
  const urlMaxAmount = searchParams.get("max_amount")
    ? Number(searchParams.get("max_amount"))
    : undefined;
  const rawProvince = searchParams.get("province_id");
  const parsedProvince = rawProvince ? parseInt(rawProvince, 10) : undefined;
  const urlProvinceId =
    parsedProvince !== undefined && !Number.isNaN(parsedProvince)
      ? parsedProvince
      : undefined;

  const rawCommune = searchParams.get("commune_id");
  const parsedCommune = rawCommune ? parseInt(rawCommune, 10) : undefined;
  const urlCommuneId =
    parsedCommune !== undefined && !Number.isNaN(parsedCommune)
      ? parsedCommune
      : undefined;

  const urlClosingFrom = searchParams.get("closing_from") ?? "";
  const urlClosingTo = searchParams.get("closing_to") ?? "";
  const urlPage = searchParams.get("page")
    ? Math.max(1, parseInt(searchParams.get("page")!, 10))
    : 1;

  // 3. Local state for input text (for debounce)
  const [inputText, setInputText] = useState(urlQuery);
  const [retryNonce, setRetryNonce] = useState(0);

  // Synchronize inputText when urlQuery changes externally (e.g. browser back/forward)
  useEffect(() => {
    setInputText(urlQuery);
  }, [urlQuery]);

  // 4. Search results & loading state
  const [state, setState] = useState<SearchState>({
    items: [],
    total: 0,
    isTruncated: false,
    isLoading: true,
    error: null,
    isServiceUnavailable: false,
  });

  // 5. Saved tenders state
  const [savedTenderIds, setSavedTenderIds] = useState<Set<string>>(new Set());
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    fetchSavedTenders()
      .then((saved) => {
        const ids = saved.map(
          (item) => item.tender?.id ?? item.tender_id ?? item.id,
        );
        setSavedTenderIds(new Set(ids));
      })
      .catch((err) => {
        console.error("Error al cargar licitaciones guardadas:", err);
      });
  }, []);

  // 6. Update URL & persist to sessionStorage helper
  const updateUrl = useCallback(
    (newParams: {
      q?: string;
      regions?: string[];
      province_id?: number;
      commune_id?: number;
      availability?: AvailabilityFilter;
      closing_from?: string;
      closing_to?: string;
      min_amount?: number;
      max_amount?: number;
      page?: number;
    }) => {
      const qVal = newParams.q !== undefined ? newParams.q : urlQuery;
      const regionsVal =
        newParams.regions !== undefined ? newParams.regions : urlRegions;
      const provinceIdVal =
        "province_id" in newParams ? newParams.province_id : urlProvinceId;
      const communeIdVal =
        "commune_id" in newParams ? newParams.commune_id : urlCommuneId;
      const availabilityVal =
        newParams.availability !== undefined
          ? newParams.availability
          : urlAvailability;
      const closingFromVal =
        newParams.closing_from !== undefined
          ? newParams.closing_from
          : urlClosingFrom;
      const closingToVal =
        newParams.closing_to !== undefined
          ? newParams.closing_to
          : urlClosingTo;
      const minVal =
        newParams.min_amount !== undefined
          ? newParams.min_amount
          : urlMinAmount;
      const maxVal =
        newParams.max_amount !== undefined
          ? newParams.max_amount
          : urlMaxAmount;
      const pageVal = newParams.page !== undefined ? newParams.page : 1;

      const sp = new URLSearchParams();
      if (qVal.trim()) sp.set("q", qVal.trim());
      for (const r of regionsVal) {
        if (r) sp.append("regions", r);
      }
      if (provinceIdVal !== undefined && provinceIdVal !== null && !isNaN(provinceIdVal)) {
        sp.set("province_id", String(provinceIdVal));
      }
      if (communeIdVal !== undefined && communeIdVal !== null && !isNaN(communeIdVal)) {
        sp.set("commune_id", String(communeIdVal));
      }
      if (availabilityVal) {
        sp.set("availability", availabilityVal);
      }
      if (closingFromVal && closingFromVal.trim()) {
        sp.set("closing_from", closingFromVal.trim());
      }
      if (closingToVal && closingToVal.trim()) {
        sp.set("closing_to", closingToVal.trim());
      }
      if (minVal !== undefined && minVal !== null && !isNaN(minVal)) {
        sp.set("min_amount", String(minVal));
      }
      if (maxVal !== undefined && maxVal !== null && !isNaN(maxVal)) {
        sp.set("max_amount", String(maxVal));
      }
      if (pageVal > 1) {
        sp.set("page", String(pageVal));
      }

      const queryString = sp.toString();

      // Persist active query to sessionStorage
      if (typeof window !== "undefined") {
        try {
          if (queryString) {
            window.sessionStorage.setItem(SEARCH_STORAGE_KEY, queryString);
          } else {
            window.sessionStorage.removeItem(SEARCH_STORAGE_KEY);
          }
        } catch {}
      }

      const target = queryString ? `${pathname}?${queryString}` : pathname;
      router.replace(target, { scroll: false });
    },
    [
      pathname,
      router,
      urlQuery,
      urlRegions,
      urlProvinceId,
      urlCommuneId,
      urlAvailability,
      urlClosingFrom,
      urlClosingTo,
      urlMinAmount,
      urlMaxAmount,
    ],
  );

  // 7. Debounce text search updates to URL
  useEffect(() => {
    if (inputText === urlQuery) return;

    const timer = setTimeout(() => {
      updateUrl({ q: inputText, page: 1 });
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [inputText, urlQuery, updateUrl]);

  // 8. Perform search query against backend
  useEffect(() => {
    let cancelled = false;

    setState((prev) => ({
      ...prev,
      isLoading: true,
      error: null,
      isServiceUnavailable: false,
    }));

    const offset = (urlPage - 1) * PAGE_SIZE;
    const params: TenderSearchParams = {
      limit: PAGE_SIZE,
      offset,
    };

    if (urlQuery.trim()) {
      params.q = urlQuery.trim();
    }
    if (urlRegions.length > 0) {
      params.regions = urlRegions;
    }
    if (urlProvinceId !== undefined) {
      params.province_id = urlProvinceId;
    }
    if (urlCommuneId !== undefined) {
      params.commune_id = urlCommuneId;
    }

    // Temporal availability & explicit date range (CA-1)
    const nowIso = new Date().toISOString();
    if (urlClosingFrom) {
      params.closing_from = urlClosingFrom.includes("T")
        ? urlClosingFrom
        : `${urlClosingFrom}T00:00:00Z`;
    } else if (urlAvailability === "vigentes") {
      params.closing_from = nowIso;
    }

    if (urlClosingTo) {
      params.closing_to = urlClosingTo.includes("T")
        ? urlClosingTo
        : `${urlClosingTo}T23:59:59Z`;
    } else if (urlAvailability === "cerradas") {
      params.closing_to = nowIso;
    }

    if (urlMinAmount !== undefined && !isNaN(urlMinAmount)) {
      params.min_amount = urlMinAmount;
    }
    if (urlMaxAmount !== undefined && !isNaN(urlMaxAmount)) {
      params.max_amount = urlMaxAmount;
    }

    searchTenders(params)
      .then((res) => {
        if (cancelled) return;
        setState({
          items: res.items,
          total: res.total,
          isTruncated: res.is_truncated ?? false,
          isLoading: false,
          error: null,
          isServiceUnavailable: false,
        });
      })
      .catch((err) => {
        if (cancelled) return;
        const is503 = err instanceof ApiError && err.status === 503;
        const message =
          err instanceof ApiError || err instanceof TimeoutError
            ? err.message
            : "No pudimos completar la búsqueda. Inténtalo nuevamente.";

        setState((prev) => ({
          ...prev,
          isLoading: false,
          error: message,
          isServiceUnavailable: is503,
        }));
      });

    return () => {
      cancelled = true;
    };
  }, [
    urlQuery,
    urlRegions,
    urlProvinceId,
    urlCommuneId,
    urlAvailability,
    urlClosingFrom,
    urlClosingTo,
    urlMinAmount,
    urlMaxAmount,
    urlPage,
    retryNonce,
  ]);

  // 9. Filter mutation handlers
  const handleSetRegions = useCallback(
    (regions: string[]) => {
      updateUrl({ regions, province_id: undefined, commune_id: undefined, page: 1 });
    },
    [updateUrl],
  );

  const handleSetProvinceId = useCallback(
    (provinceId?: number) => {
      updateUrl({ province_id: provinceId, commune_id: undefined, page: 1 });
    },
    [updateUrl],
  );

  const handleSetCommuneId = useCallback(
    (communeId?: number) => {
      updateUrl({ commune_id: communeId, page: 1 });
    },
    [updateUrl],
  );

  const handleSetAvailability = useCallback(
    (availability: AvailabilityFilter) => {
      updateUrl({ availability, page: 1 });
    },
    [updateUrl],
  );

  const handleSetAmountRange = useCallback(
    (min?: number, max?: number) => {
      updateUrl({ min_amount: min, max_amount: max, page: 1 });
    },
    [updateUrl],
  );

  const handleSetClosingDateRange = useCallback(
    (from?: string, to?: string) => {
      updateUrl({
        closing_from: from ?? "",
        closing_to: to ?? "",
        page: 1,
      });
    },
    [updateUrl],
  );

  const handleSetPage = useCallback(
    (page: number) => {
      updateUrl({ page });
    },
    [updateUrl],
  );

  const handleClearFilters = useCallback(() => {
    if (typeof window !== "undefined") {
      try {
        window.sessionStorage.removeItem(SEARCH_STORAGE_KEY);
      } catch {}
    }
    setInputText("");
    router.replace(pathname, { scroll: false });
  }, [pathname, router]);

  const handleRetry = useCallback(() => {
    setRetryNonce((n) => n + 1);
  }, []);

  const handleToggleSave = useCallback(
    async (tenderId: string) => {
      const isCurrentlySaved = savedTenderIds.has(tenderId);
      setActionError(null);

      // Optimistic update
      setSavedTenderIds((prev) => {
        const next = new Set(prev);
        if (isCurrentlySaved) next.delete(tenderId);
        else next.add(tenderId);
        return next;
      });

      try {
        if (isCurrentlySaved) {
          await unsaveTenderApi(tenderId);
        } else {
          await saveTenderApi(tenderId);
        }
      } catch (err) {
        console.error("Error al actualizar guardado:", err);
        setSavedTenderIds((prev) => {
          const next = new Set(prev);
          if (isCurrentlySaved) next.add(tenderId);
          else next.delete(tenderId);
          return next;
        });
        setActionError(
          err instanceof ApiError
            ? err.message
            : "No pudimos guardar los cambios. Revisa tu conexión.",
        );
      }
    },
    [savedTenderIds],
  );

  const activeFilterCount =
    urlRegions.length +
    (urlProvinceId !== undefined ? 1 : 0) +
    (urlCommuneId !== undefined ? 1 : 0) +
    (urlAvailability !== null ? 1 : 0) +
    (urlClosingFrom ? 1 : 0) +
    (urlClosingTo ? 1 : 0) +
    (urlMinAmount !== undefined ? 1 : 0) +
    (urlMaxAmount !== undefined ? 1 : 0);

  const hasActiveFilters = Boolean(
    urlQuery.trim() || activeFilterCount > 0,
  );

  return {
    inputText,
    setInputText,
    query: urlQuery,
    regions: urlRegions,
    setRegions: handleSetRegions,
    provinceId: urlProvinceId,
    setProvinceId: handleSetProvinceId,
    communeId: urlCommuneId,
    setCommuneId: handleSetCommuneId,
    availability: urlAvailability,
    setAvailability: handleSetAvailability,
    closingFrom: urlClosingFrom,
    closingTo: urlClosingTo,
    setClosingDateRange: handleSetClosingDateRange,
    minAmount: urlMinAmount,
    maxAmount: urlMaxAmount,
    setAmountRange: handleSetAmountRange,
    page: urlPage,
    setPage: handleSetPage,
    pageSize: PAGE_SIZE,
    clearFilters: handleClearFilters,
    hasActiveFilters,
    activeFilterCount,
    state,
    retry: handleRetry,
    savedTenderIds,
    toggleSave: handleToggleSave,
    actionError,
    clearActionError: () => setActionError(null),
  };
}
