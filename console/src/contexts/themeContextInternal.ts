import { createContext, useContext } from "react";

export type ThemeMode = "light" | "dark" | "system";

export interface ThemeContextValue {
  themeMode: ThemeMode;
  isDark: boolean;
  setThemeMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue>({
  themeMode: "light",
  isDark: false,
  setThemeMode: () => {},
  toggleTheme: () => {},
});

export const THEME_STORAGE_KEY = "copaw-theme";

export function getInitialMode(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    // ignore storage errors
  }
  return "system";
}

export function resolveIsDark(mode: ThemeMode): boolean {
  if (mode === "dark") return true;
  if (mode === "light") return false;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext);
}
