import { createGlobalStyle } from "antd-style";
import { ConfigProvider, bailianTheme } from "@agentscope-ai/design";
import { message } from "antd";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useEffect, useMemo, useState, lazy, Suspense } from "react";
import { useTranslation } from "react-i18next";
import zhCN from "antd/locale/zh_CN";
import enUS from "antd/locale/en_US";
import jaJP from "antd/locale/ja_JP";
import ruRU from "antd/locale/ru_RU";
import type { Locale } from "antd/es/locale";
import { theme as antdTheme } from "antd";
import dayjs from "dayjs";
import "dayjs/locale/zh-cn";
import "dayjs/locale/ja";
import "dayjs/locale/ru";
import { ThemeProvider } from "./contexts/ThemeContext";
import { useTheme } from "./contexts/useTheme";
import { authApi } from "./api/modules/auth";
import { getApiUrl, getApiToken, clearAuthToken } from "./api/config";
import "./styles/layout.css";
import "./styles/form-override.css";

const MainLayout = lazy(() => import("./layouts/MainLayout"));
const LoginPage = lazy(() => import("./pages/Login"));

// Configure message global settings
message.config({
  top: 24,
  duration: 3,
  maxCount: 3,
});

const antdLocaleMap: Record<string, Locale> = {
  zh: zhCN,
  en: enUS,
  ja: jaJP,
  ru: ruRU,
};

const dayjsLocaleMap: Record<string, string> = {
  zh: "zh-cn",
  en: "en",
  ja: "ja",
  ru: "ru",
};

const baseThemeConfig = bailianTheme as typeof bailianTheme & {
  theme?: {
    token?: Record<string, unknown>;
    components?: Record<string, unknown>;
  };
};

const GlobalStyle = createGlobalStyle`
* {
  margin: 0;
  box-sizing: border-box;
}
`;

function AuthGuard({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<"loading" | "auth-required" | "ok">(
    "loading",
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await authApi.getStatus();
        if (cancelled) return;
        if (!res.enabled) {
          setStatus("ok");
          return;
        }
        const token = getApiToken();
        if (!token) {
          setStatus("auth-required");
          return;
        }
        try {
          const r = await fetch(getApiUrl("/auth/verify"), {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (cancelled) return;
          if (r.ok) {
            setStatus("ok");
          } else {
            clearAuthToken();
            setStatus("auth-required");
          }
        } catch {
          if (!cancelled) {
            clearAuthToken();
            setStatus("auth-required");
          }
        }
      } catch {
        if (!cancelled) setStatus("ok");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === "loading") return null;
  if (status === "auth-required")
    return (
      <Navigate
        to={`/login?redirect=${encodeURIComponent(window.location.pathname)}`}
        replace
      />
    );
  return <>{children}</>;
}

function getRouterBasename(pathname: string): string | undefined {
  return /^\/console(?:\/|$)/.test(pathname) ? "/console" : undefined;
}

function AppInner() {
  const basename = getRouterBasename(window.location.pathname);
  const { i18n, t } = useTranslation();
  const { isDark } = useTheme();
  const lang = i18n.resolvedLanguage || i18n.language || "en";
  const colorPrimary = isDark ? "#67a7c0" : "#1f5e78";
  const colorPrimaryHover = isDark ? "#84c2da" : "#184a60";
  const colorBorder = isDark
    ? "rgba(103, 167, 192, 0.16)"
    : "rgba(15, 23, 42, 0.08)";
  const colorBgElevated = isDark
    ? "rgba(10, 24, 32, 0.92)"
    : "rgba(255, 255, 255, 0.94)";
  const [antdLocale, setAntdLocale] = useState<Locale>(
    antdLocaleMap[lang] ?? enUS,
  );
  const loadingFallback = (
    <div className="screen-loading">{t("common.loading")}</div>
  );
  const providerTheme = useMemo(
    () => ({
      ...baseThemeConfig.theme,
      algorithm: isDark
        ? antdTheme.darkAlgorithm
        : antdTheme.defaultAlgorithm,
      token: {
        ...(baseThemeConfig.theme?.token ?? {}),
        colorPrimary,
        colorInfo: colorPrimary,
        colorLink: colorPrimary,
        colorLinkHover: colorPrimaryHover,
        colorBgLayout: "transparent",
        colorBgElevated,
        colorBorder,
        borderRadius: 14,
        borderRadiusLG: 18,
        borderRadiusSM: 10,
        fontFamily:
          '"IBM Plex Sans", "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif',
      },
      components: {
        ...(baseThemeConfig.theme?.components ?? {}),
        Layout: {
          bodyBg: "transparent",
          headerBg: "transparent",
          siderBg: "transparent",
        },
        Card: {
          colorBgContainer: "transparent",
        },
        Menu: {
          itemBg: "transparent",
          subMenuItemBg: "transparent",
          itemSelectedBg: isDark
            ? "rgba(103, 167, 192, 0.16)"
            : "rgba(31, 94, 120, 0.12)",
          itemHoverBg: isDark
            ? "rgba(255, 255, 255, 0.04)"
            : "rgba(31, 94, 120, 0.06)",
          itemColor: isDark ? "#b8cbd4" : "#475467",
          itemSelectedColor: colorPrimary,
        },
        Table: {
          headerBg: isDark
            ? "linear-gradient(180deg, #1d2730 0%, #192129 100%)"
            : "linear-gradient(180deg, #f8fafc 0%, #f3f6fb 100%)",
          headerColor: isDark ? "rgba(255, 255, 255, 0.72)" : "#475467",
          rowHoverBg: isDark
            ? "rgba(61, 143, 170, 0.12)"
            : "rgba(31, 94, 120, 0.05)",
        },
      },
    }),
    [colorBgElevated, colorBorder, colorPrimary, colorPrimaryHover, isDark],
  );

  useEffect(() => {
    const handleLanguageChanged = (lng: string) => {
      const shortLng = lng.split("-")[0];
      setAntdLocale(antdLocaleMap[shortLng] ?? enUS);
      dayjs.locale(dayjsLocaleMap[shortLng] ?? "en");
    };

    // Set initial dayjs locale
    dayjs.locale(dayjsLocaleMap[lang.split("-")[0]] ?? "en");

    i18n.on("languageChanged", handleLanguageChanged);
    return () => {
      i18n.off("languageChanged", handleLanguageChanged);
    };
  }, [i18n, lang]);

  return (
    <BrowserRouter basename={basename}>
      <GlobalStyle />
      <ConfigProvider
        {...bailianTheme}
        prefix="copaw"
        prefixCls="copaw"
        locale={antdLocale}
        theme={providerTheme}
      >
        <div className="app-shell">
          <Routes>
            <Route
              path="/login"
              element={
                <Suspense fallback={loadingFallback}>
                  <LoginPage />
                </Suspense>
              }
            />
            <Route
              path="/*"
              element={
                <AuthGuard>
                  <Suspense fallback={loadingFallback}>
                    <MainLayout />
                  </Suspense>
                </AuthGuard>
              }
            />
          </Routes>
        </div>
      </ConfigProvider>
    </BrowserRouter>
  );
}

function App() {
  return (
    <ThemeProvider>
      <AppInner />
    </ThemeProvider>
  );
}

export default App;
