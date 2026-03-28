import {
  startTransition,
  useEffect,
  useCallback,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ThemeContext,
  THEME_STORAGE_KEY,
  getInitialMode,
  resolveIsDark,
  type ThemeMode,
} from "./themeContextInternal";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(getInitialMode);
  const [systemDark, setSystemDark] = useState<boolean>(() =>
    resolveIsDark(getInitialMode()),
  );
  const isDark = themeMode === "system" ? systemDark : themeMode === "dark";

  // Apply dark/light class to <html> element for global CSS variable overrides
  useEffect(() => {
    const html = document.documentElement;
    const body = document.body;
    if (isDark) {
      html.classList.add("dark-mode");
      body.dataset.appTheme = "night";
    } else {
      html.classList.remove("dark-mode");
      body.dataset.appTheme = "day";
    }
  }, [isDark]);

  // Listen to system theme changes when mode is "system"
  useEffect(() => {
    if (themeMode !== "system") return;

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemDark(mq.matches);
    const handler = (e: MediaQueryListEvent) => {
      setSystemDark(e.matches);
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [themeMode]);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    startTransition(() => {
      setThemeModeState(mode);
      if (mode === "system") {
        setSystemDark(resolveIsDark(mode));
      }
    });
    try {
      localStorage.setItem(THEME_STORAGE_KEY, mode);
    } catch {
      // ignore
    }
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeMode(isDark ? "light" : "dark");
  }, [isDark, setThemeMode]);
  const contextValue = useMemo(
    () => ({ themeMode, isDark, setThemeMode, toggleTheme }),
    [themeMode, isDark, setThemeMode, toggleTheme],
  );

  return (
    <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>
  );
}
