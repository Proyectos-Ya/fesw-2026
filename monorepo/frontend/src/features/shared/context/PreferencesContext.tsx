"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type ThemeMode = "light" | "dark";
export type FontScale = "normal" | "large" | "xlarge";

export const THEME_STORAGE_KEY = "chiripa_theme";
export const FONT_SCALE_STORAGE_KEY = "chiripa_font_scale";

export const FONT_SCALE_PERCENT: Record<FontScale, string> = {
  normal: "100%",
  large: "112.5%",
  xlarge: "125%",
};

export interface PreferencesContextValue {
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
  toggleTheme: () => void;
  fontScale: FontScale;
  setFontScale: (scale: FontScale) => void;
}

const PreferencesContext = createContext<PreferencesContextValue | null>(null);

function isValidTheme(value: string | null): value is ThemeMode {
  return value === "light" || value === "dark";
}

function isValidFontScale(value: string | null): value is FontScale {
  return value === "normal" || value === "large" || value === "xlarge";
}

function applyThemeToDom(theme: ThemeMode) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.setAttribute("data-theme", theme);
}

function applyFontScaleToDom(fontScale: FontScale) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-font-scale", fontScale);
  root.style.fontSize = FONT_SCALE_PERCENT[fontScale];
}

function readStoredTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (isValidTheme(stored)) return stored;
  } catch {
    // Ignore storage access errors
  }
  return "light";
}

function readStoredFontScale(): FontScale {
  if (typeof window === "undefined") return "normal";
  try {
    const stored = window.localStorage.getItem(FONT_SCALE_STORAGE_KEY);
    if (isValidFontScale(stored)) return stored;
  } catch {
    // Ignore storage access errors
  }
  return "normal";
}

function usePreferencesState(): PreferencesContextValue {
  const [theme, setThemeState] = useState<ThemeMode>("light");
  const [fontScale, setFontScaleState] = useState<FontScale>("normal");

  useEffect(() => {
    const initialTheme = readStoredTheme();
    const initialScale = readStoredFontScale();
    setThemeState(initialTheme);
    setFontScaleState(initialScale);
    applyThemeToDom(initialTheme);
    applyFontScaleToDom(initialScale);
  }, []);

  const setTheme = useCallback((nextTheme: ThemeMode) => {
    setThemeState(nextTheme);
    applyThemeToDom(nextTheme);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch {
      // Ignore storage access errors
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next: ThemeMode = prev === "dark" ? "light" : "dark";
      applyThemeToDom(next);
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Ignore storage access errors
      }
      return next;
    });
  }, []);

  const setFontScale = useCallback((nextScale: FontScale) => {
    setFontScaleState(nextScale);
    applyFontScaleToDom(nextScale);
    try {
      window.localStorage.setItem(FONT_SCALE_STORAGE_KEY, nextScale);
    } catch {
      // Ignore storage access errors
    }
  }, []);

  return useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
      fontScale,
      setFontScale,
    }),
    [theme, setTheme, toggleTheme, fontScale, setFontScale],
  );
}

export function PreferencesProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const value = usePreferencesState();

  return (
    <PreferencesContext.Provider value={value}>
      {children}
    </PreferencesContext.Provider>
  );
}

export function usePreferences(): PreferencesContextValue {
  const context = useContext(PreferencesContext);
  const fallback = usePreferencesState();
  return context ?? fallback;
}
