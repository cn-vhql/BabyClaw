export type ChatThemeKey = "brand" | "ocean" | "forest" | "sunset";

export interface ChatThemePalette {
  colorPrimary: string;
  colorBgBase: string;
  colorTextBase: string;
  background: string;
  shellBackground: string;
  panelBackground: string;
  headerBackground: string;
  headerBorder: string;
  borderColor: string;
  borderSoftColor: string;
  shadowColor: string;
  assistantBubble: string;
  senderBackground: string;
  promptBackground: string;
  promptHoverBackground: string;
  conversationHover: string;
  conversationActive: string;
  scrollThumb: string;
  themePickerAccent: string;
  assistantText: string;
  assistantHeading: string;
  assistantLink: string;
  assistantSurface: string;
  assistantBorder: string;
  assistantShadow: string;
  assistantRadius: string;
  assistantPadding: string;
  assistantBackdropFilter: string;
  assistantFontFamily: string;
  assistantH1Border: string;
  assistantH2Bg: string;
  assistantH2Text: string;
  assistantH2Border: string;
  assistantH2Shadow: string;
  assistantH3Accent: string;
  assistantH3Glow: string;
  assistantH4Text: string;
  assistantStrongBg: string;
  assistantStrongText: string;
  assistantEmphasis: string;
  assistantMarker: string;
  assistantMarkBg: string;
  assistantMarkText: string;
  assistantBlockquoteBg: string;
  assistantQuoteBorder: string;
  assistantInlineCodeBg: string;
  assistantInlineCodeBorder: string;
  assistantCodeBg: string;
  assistantCodeHeader: string;
  assistantCodeText: string;
  assistantTableBg: string;
  assistantTableHeadBg: string;
  assistantTableHeadText: string;
  assistantTableBorder: string;
  assistantHr: string;
  assistantImageShadow: string;
}

interface ChatThemeDefinition {
  preview: string;
  light: ChatThemePalette;
  dark: ChatThemePalette;
}

export const DEFAULT_CHAT_THEME: ChatThemeKey = "brand";
export const CHAT_THEME_STORAGE_KEY = "copaw-chat-theme-preset";

const CHAT_THEMES: Record<ChatThemeKey, ChatThemeDefinition> = {
  brand: {
    preview:
      "linear-gradient(180deg, #f4f9fb 0%, #edf5f9 42%, #ffffff 100%)",
    light: {
      colorPrimary: "#1f5e78",
      colorBgBase: "#f4f9fb",
      colorTextBase: "#173344",
      background:
        "linear-gradient(180deg, rgba(244, 249, 251, 0.96) 0%, rgba(237, 245, 249, 0.92) 42%, #ffffff 100%), linear-gradient(90deg, rgba(31, 94, 120, 0.035) 1px, transparent 1px), linear-gradient(0deg, rgba(31, 94, 120, 0.03) 1px, transparent 1px)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(31, 94, 120, 0.14), transparent 32%), radial-gradient(circle at 100% 18%, rgba(45, 124, 149, 0.14), transparent 22%), linear-gradient(180deg, #f4f9fb 0%, #edf4f7 48%, #ffffff 100%)",
      panelBackground: "rgba(255, 255, 255, 0.82)",
      headerBackground: "rgba(244, 250, 252, 0.82)",
      headerBorder: "rgba(31, 94, 120, 0.12)",
      borderColor: "rgba(31, 94, 120, 0.14)",
      borderSoftColor: "rgba(31, 94, 120, 0.08)",
      shadowColor: "rgba(24, 74, 96, 0.12)",
      assistantBubble: "rgba(255, 255, 255, 0.98)",
      senderBackground: "rgba(255, 255, 255, 0.94)",
      promptBackground: "rgba(255, 255, 255, 0.84)",
      promptHoverBackground: "#edf6f9",
      conversationHover: "rgba(31, 94, 120, 0.06)",
      conversationActive: "rgba(31, 94, 120, 0.12)",
      scrollThumb: "rgba(31, 94, 120, 0.24)",
      themePickerAccent: "#1f5e78",
      assistantText: "#173344",
      assistantHeading: "#102736",
      assistantLink: "#1f5e78",
      assistantSurface:
        "linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(242, 249, 252, 0.96) 100%)",
      assistantBorder: "rgba(31, 94, 120, 0.14)",
      assistantShadow: "0 18px 40px rgba(24, 74, 96, 0.1)",
      assistantRadius: "18px",
      assistantPadding: "20px 24px 22px",
      assistantBackdropFilter: "blur(10px) saturate(132%)",
      assistantFontFamily:
        '"IBM Plex Sans", "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif',
      assistantH1Border: "rgba(31, 94, 120, 0.18)",
      assistantH2Bg: "linear-gradient(135deg, #1f5e78 0%, #2d7c95 100%)",
      assistantH2Text: "#f7fcff",
      assistantH2Border: "rgba(15, 59, 77, 0.12)",
      assistantH2Shadow: "0 12px 26px rgba(31, 94, 120, 0.2)",
      assistantH3Accent: "#2d7c95",
      assistantH3Glow: "0 0 0 6px rgba(31, 94, 120, 0.12)",
      assistantH4Text: "#3c7084",
      assistantStrongBg: "rgba(31, 94, 120, 0.12)",
      assistantStrongText: "#12455a",
      assistantEmphasis: "#2b6d84",
      assistantMarker: "#2d7c95",
      assistantMarkBg: "rgba(31, 94, 120, 0.16)",
      assistantMarkText: "#15384a",
      assistantBlockquoteBg: "rgba(232, 244, 248, 0.9)",
      assistantQuoteBorder: "#2d7c95",
      assistantInlineCodeBg: "rgba(31, 94, 120, 0.08)",
      assistantInlineCodeBorder: "rgba(31, 94, 120, 0.14)",
      assistantCodeBg: "#10212d",
      assistantCodeHeader: "#0d1a24",
      assistantCodeText: "#dcf4ff",
      assistantTableBg: "rgba(255, 255, 255, 0.98)",
      assistantTableHeadBg: "#e9f4f8",
      assistantTableHeadText: "#143849",
      assistantTableBorder: "#d4e7ee",
      assistantHr: "rgba(31, 94, 120, 0.16)",
      assistantImageShadow: "0 12px 30px rgba(31, 94, 120, 0.16)",
    },
    dark: {
      colorPrimary: "#67a7c0",
      colorBgBase: "#09131a",
      colorTextBase: "#e8f7fc",
      background:
        "linear-gradient(180deg, rgba(9, 19, 26, 0.98) 0%, rgba(10, 24, 32, 0.98) 100%), linear-gradient(90deg, rgba(103, 167, 192, 0.06) 1px, transparent 1px), linear-gradient(0deg, rgba(103, 167, 192, 0.05) 1px, transparent 1px)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(103, 167, 192, 0.24), transparent 28%), radial-gradient(circle at 100% 16%, rgba(31, 94, 120, 0.24), transparent 24%), linear-gradient(180deg, #061118 0%, #0c1a22 100%)",
      panelBackground: "#0b1820",
      headerBackground: "#08141b",
      headerBorder: "#26414c",
      borderColor: "#2a4754",
      borderSoftColor: "#203742",
      shadowColor: "rgba(0, 8, 12, 0.5)",
      assistantBubble: "#0d1c24",
      senderBackground: "#0a1820",
      promptBackground: "#10212a",
      promptHoverBackground: "#142b36",
      conversationHover: "#10212a",
      conversationActive: "#15313e",
      scrollThumb: "rgba(103, 167, 192, 0.28)",
      themePickerAccent: "#67a7c0",
      assistantText: "#d9eff7",
      assistantHeading: "#f3fbff",
      assistantLink: "#84c2da",
      assistantSurface: "linear-gradient(180deg, #102029 0%, #0a1820 100%)",
      assistantBorder: "#2a4754",
      assistantShadow: "0 24px 52px rgba(0, 8, 12, 0.44)",
      assistantRadius: "18px",
      assistantPadding: "20px 24px 22px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        '"IBM Plex Sans", "Segoe UI", "PingFang SC", "Helvetica Neue", sans-serif',
      assistantH1Border: "#2d4d5a",
      assistantH2Bg: "linear-gradient(135deg, #205d74 0%, #2f7993 100%)",
      assistantH2Text: "#f3fbff",
      assistantH2Border: "#3b6778",
      assistantH2Shadow: "0 12px 30px rgba(0, 0, 0, 0.28)",
      assistantH3Accent: "#67a7c0",
      assistantH3Glow: "0 0 0 6px rgba(103, 167, 192, 0.14)",
      assistantH4Text: "#8eb8c8",
      assistantStrongBg: "#173441",
      assistantStrongText: "#f0fbff",
      assistantEmphasis: "#9acfe2",
      assistantMarker: "#76bad4",
      assistantMarkBg: "#1b3a48",
      assistantMarkText: "#f2fbff",
      assistantBlockquoteBg: "#122732",
      assistantQuoteBorder: "#67a7c0",
      assistantInlineCodeBg: "#142a35",
      assistantInlineCodeBorder: "#294958",
      assistantCodeBg: "#08161d",
      assistantCodeHeader: "#061118",
      assistantCodeText: "#d7f0fb",
      assistantTableBg: "#0b1820",
      assistantTableHeadBg: "#132b36",
      assistantTableHeadText: "#e8f7fc",
      assistantTableBorder: "#2a4754",
      assistantHr: "#2a4754",
      assistantImageShadow: "0 14px 34px rgba(0, 8, 12, 0.4)",
    },
  },
  ocean: {
    preview:
      "radial-gradient(circle at top, #f4f7ff 0%, #edf2ff 38%, #ffffff 100%)",
    light: {
      colorPrimary: "#7388ff",
      colorBgBase: "#f4f7ff",
      colorTextBase: "#23304b",
      background:
        "radial-gradient(circle at top, #f4f7ff 0%, #edf2ff 38%, #ffffff 100%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(120, 137, 255, 0.14), transparent 30%), radial-gradient(circle at 100% 18%, rgba(167, 139, 250, 0.12), transparent 20%), linear-gradient(180deg, #f4f7ff 0%, #edf2ff 38%, #ffffff 100%)",
      panelBackground: "rgba(255, 255, 255, 0.74)",
      headerBackground: "rgba(247, 249, 255, 0.66)",
      headerBorder: "rgba(120, 137, 255, 0.12)",
      borderColor: "rgba(120, 137, 255, 0.14)",
      borderSoftColor: "rgba(120, 137, 255, 0.1)",
      shadowColor: "rgba(120, 137, 255, 0.15)",
      assistantBubble: "rgba(255, 255, 255, 0.84)",
      senderBackground: "rgba(255, 255, 255, 0.92)",
      promptBackground: "rgba(255, 255, 255, 0.78)",
      promptHoverBackground: "rgba(245, 248, 255, 0.98)",
      conversationHover: "rgba(120, 137, 255, 0.08)",
      conversationActive: "rgba(120, 137, 255, 0.14)",
      scrollThumb: "rgba(120, 137, 255, 0.28)",
      themePickerAccent: "#7889ff",
      assistantText: "#23304b",
      assistantHeading: "#1f2840",
      assistantLink: "#5e73f7",
      assistantSurface:
        "linear-gradient(180deg, rgba(255, 255, 255, 0.8) 0%, rgba(245, 248, 255, 0.66) 100%)",
      assistantBorder: "rgba(255, 255, 255, 0.82)",
      assistantShadow: "0 18px 46px rgba(120, 137, 255, 0.15)",
      assistantRadius: "24px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "blur(18px) saturate(145%)",
      assistantFontFamily:
        '"Avenir Next", "SF Pro Display", "PingFang SC", "Segoe UI", sans-serif',
      assistantH1Border: "rgba(120, 137, 255, 0.16)",
      assistantH2Bg: "linear-gradient(135deg, #7388ff 0%, #a78bfa 100%)",
      assistantH2Text: "#fdfdff",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 14px 30px rgba(120, 137, 255, 0.22)",
      assistantH3Accent: "#7388ff",
      assistantH3Glow: "0 0 0 6px rgba(120, 137, 255, 0.16)",
      assistantH4Text: "#6076f4",
      assistantStrongBg: "rgba(120, 137, 255, 0.12)",
      assistantStrongText: "#324ab9",
      assistantEmphasis: "#5a72f4",
      assistantMarker: "#7f8fff",
      assistantMarkBg: "rgba(120, 137, 255, 0.16)",
      assistantMarkText: "#24314c",
      assistantBlockquoteBg: "rgba(255, 255, 255, 0.54)",
      assistantQuoteBorder: "#8090ff",
      assistantInlineCodeBg: "rgba(94, 115, 247, 0.08)",
      assistantInlineCodeBorder: "rgba(94, 115, 247, 0.12)",
      assistantCodeBg: "#1d2333",
      assistantCodeHeader: "#161b28",
      assistantCodeText: "#eef3ff",
      assistantTableBg: "rgba(255, 255, 255, 0.9)",
      assistantTableHeadBg: "rgba(120, 137, 255, 0.1)",
      assistantTableHeadText: "#2b3862",
      assistantTableBorder: "rgba(120, 137, 255, 0.14)",
      assistantHr: "rgba(120, 137, 255, 0.16)",
      assistantImageShadow: "0 12px 34px rgba(120, 137, 255, 0.16)",
    },
    dark: {
      colorPrimary: "#95a2ff",
      colorBgBase: "#111728",
      colorTextBase: "#edf1ff",
      background:
        "radial-gradient(circle at top left, rgba(149, 162, 255, 0.18), transparent 30%), linear-gradient(180deg, #0f1524 0%, #151d31 100%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(149, 162, 255, 0.22), transparent 26%), radial-gradient(circle at 100% 16%, rgba(167, 139, 250, 0.16), transparent 24%), linear-gradient(180deg, #0e1422 0%, #151d31 100%)",
      panelBackground: "#121a2d",
      headerBackground: "#0e1526",
      headerBorder: "#404b78",
      borderColor: "#465280",
      borderSoftColor: "#313b63",
      shadowColor: "rgba(2, 6, 18, 0.48)",
      assistantBubble: "#151f34",
      senderBackground: "#121a2d",
      promptBackground: "#19233c",
      promptHoverBackground: "#223055",
      conversationHover: "#19233c",
      conversationActive: "#223055",
      scrollThumb: "rgba(149, 162, 255, 0.28)",
      themePickerAccent: "#95a2ff",
      assistantText: "#e6ebff",
      assistantHeading: "#f7f8ff",
      assistantLink: "#aab4ff",
      assistantSurface: "linear-gradient(180deg, #18233c 0%, #11192b 100%)",
      assistantBorder: "#465280",
      assistantShadow: "0 24px 54px rgba(2, 6, 18, 0.42)",
      assistantRadius: "24px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        '"Avenir Next", "SF Pro Display", "PingFang SC", "Segoe UI", sans-serif',
      assistantH1Border: "#4c5886",
      assistantH2Bg: "linear-gradient(135deg, #5f72df 0%, #8f77e7 100%)",
      assistantH2Text: "#fdfdff",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 14px 30px rgba(2, 6, 18, 0.32)",
      assistantH3Accent: "#95a2ff",
      assistantH3Glow: "0 0 0 6px rgba(149, 162, 255, 0.14)",
      assistantH4Text: "#acb6ff",
      assistantStrongBg: "#233055",
      assistantStrongText: "#f3f5ff",
      assistantEmphasis: "#c0c8ff",
      assistantMarker: "#aab4ff",
      assistantMarkBg: "#293762",
      assistantMarkText: "#f4f6ff",
      assistantBlockquoteBg: "#17213a",
      assistantQuoteBorder: "#95a2ff",
      assistantInlineCodeBg: "#1c2946",
      assistantInlineCodeBorder: "#465280",
      assistantCodeBg: "#111728",
      assistantCodeHeader: "#0b1020",
      assistantCodeText: "#edf1ff",
      assistantTableBg: "#141d33",
      assistantTableHeadBg: "#223055",
      assistantTableHeadText: "#ecf0ff",
      assistantTableBorder: "#465280",
      assistantHr: "#465280",
      assistantImageShadow: "0 14px 34px rgba(2, 6, 18, 0.36)",
    },
  },
  forest: {
    preview: "linear-gradient(180deg, #f4f8f1 0%, #fcfefb 54%, #ffffff 100%)",
    light: {
      colorPrimary: "#5d7c6c",
      colorBgBase: "#f4f8f1",
      colorTextBase: "#253126",
      background:
        "linear-gradient(180deg, #f4f8f1 0%, #fcfefb 54%, #ffffff 100%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(107, 139, 120, 0.12), transparent 28%), radial-gradient(circle at 100% 18%, rgba(137, 160, 131, 0.12), transparent 24%), linear-gradient(180deg, #f4f8f1 0%, #fcfefb 54%, #ffffff 100%)",
      panelBackground: "rgba(255, 255, 255, 0.78)",
      headerBackground: "rgba(247, 250, 244, 0.84)",
      headerBorder: "rgba(107, 139, 120, 0.12)",
      borderColor: "rgba(107, 139, 120, 0.14)",
      borderSoftColor: "rgba(107, 139, 120, 0.08)",
      shadowColor: "rgba(92, 124, 104, 0.12)",
      assistantBubble: "rgba(255, 255, 253, 0.96)",
      senderBackground: "rgba(255, 255, 255, 0.94)",
      promptBackground: "rgba(255, 255, 255, 0.8)",
      promptHoverBackground: "#f1f7ef",
      conversationHover: "rgba(107, 139, 120, 0.08)",
      conversationActive: "rgba(107, 139, 120, 0.14)",
      scrollThumb: "rgba(107, 139, 120, 0.28)",
      themePickerAccent: "#6b8b78",
      assistantText: "#253126",
      assistantHeading: "#223024",
      assistantLink: "#557362",
      assistantSurface: "linear-gradient(180deg, #fffffd 0%, #f5faef 100%)",
      assistantBorder: "#dae6d7",
      assistantShadow: "0 16px 34px rgba(92, 124, 104, 0.12)",
      assistantRadius: "22px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        '"Palatino Linotype", "Noto Serif SC", "PingFang SC", Georgia, serif',
      assistantH1Border: "rgba(107, 139, 120, 0.16)",
      assistantH2Bg: "linear-gradient(135deg, #5d7c6c 0%, #89a083 100%)",
      assistantH2Text: "#fdfefb",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 12px 26px rgba(93, 124, 108, 0.18)",
      assistantH3Accent: "#6b8b78",
      assistantH3Glow: "0 0 0 6px rgba(107, 139, 120, 0.14)",
      assistantH4Text: "#4f6a5b",
      assistantStrongBg: "rgba(93, 124, 108, 0.14)",
      assistantStrongText: "#3a5445",
      assistantEmphasis: "#5c7b6b",
      assistantMarker: "#6b8b78",
      assistantMarkBg: "rgba(107, 139, 120, 0.18)",
      assistantMarkText: "#203024",
      assistantBlockquoteBg: "#f0f6ee",
      assistantQuoteBorder: "#6b8b78",
      assistantInlineCodeBg: "rgba(93, 124, 108, 0.1)",
      assistantInlineCodeBorder: "rgba(93, 124, 108, 0.14)",
      assistantCodeBg: "#243029",
      assistantCodeHeader: "#1d2621",
      assistantCodeText: "#edf6ec",
      assistantTableBg: "#fffffd",
      assistantTableHeadBg: "#edf5eb",
      assistantTableHeadText: "#2f4637",
      assistantTableBorder: "#d5e2d3",
      assistantHr: "rgba(93, 124, 108, 0.18)",
      assistantImageShadow: "0 10px 28px rgba(93, 124, 108, 0.14)",
    },
    dark: {
      colorPrimary: "#8fb29a",
      colorBgBase: "#101712",
      colorTextBase: "#eef7f1",
      background:
        "radial-gradient(circle at top left, rgba(143, 178, 154, 0.18), transparent 28%), linear-gradient(180deg, #0c130f 0%, #121a15 100%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(143, 178, 154, 0.2), transparent 26%), radial-gradient(circle at 100% 16%, rgba(107, 139, 120, 0.18), transparent 22%), linear-gradient(180deg, #09120d 0%, #101912 100%)",
      panelBackground: "#102018",
      headerBackground: "#0d1a13",
      headerBorder: "#375246",
      borderColor: "#3b584a",
      borderSoftColor: "#294137",
      shadowColor: "rgba(1, 10, 5, 0.46)",
      assistantBubble: "#14241b",
      senderBackground: "#102018",
      promptBackground: "#182922",
      promptHoverBackground: "#23372b",
      conversationHover: "#15251d",
      conversationActive: "#20362b",
      scrollThumb: "rgba(143, 178, 154, 0.28)",
      themePickerAccent: "#8fb29a",
      assistantText: "#ebf7ee",
      assistantHeading: "#f7fdf8",
      assistantLink: "#a8cab2",
      assistantSurface: "linear-gradient(180deg, #172b20 0%, #102018 100%)",
      assistantBorder: "#3b584a",
      assistantShadow: "0 24px 50px rgba(1, 10, 5, 0.4)",
      assistantRadius: "22px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        '"Palatino Linotype", "Noto Serif SC", "PingFang SC", Georgia, serif',
      assistantH1Border: "#426252",
      assistantH2Bg: "linear-gradient(135deg, #557362 0%, #6f8f79 100%)",
      assistantH2Text: "#f6fbf7",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 12px 28px rgba(1, 10, 5, 0.26)",
      assistantH3Accent: "#8fb29a",
      assistantH3Glow: "0 0 0 6px rgba(143, 178, 154, 0.14)",
      assistantH4Text: "#abc7b3",
      assistantStrongBg: "#20362a",
      assistantStrongText: "#f0faf2",
      assistantEmphasis: "#bfdbc6",
      assistantMarker: "#a1c5ab",
      assistantMarkBg: "#274032",
      assistantMarkText: "#f3fbf5",
      assistantBlockquoteBg: "#192f23",
      assistantQuoteBorder: "#8fb29a",
      assistantInlineCodeBg: "#203126",
      assistantInlineCodeBorder: "#3b584a",
      assistantCodeBg: "#111b14",
      assistantCodeHeader: "#0c140f",
      assistantCodeText: "#ebf7ee",
      assistantTableBg: "#13231b",
      assistantTableHeadBg: "#21352a",
      assistantTableHeadText: "#ebf7ee",
      assistantTableBorder: "#3b584a",
      assistantHr: "#3b584a",
      assistantImageShadow: "0 14px 34px rgba(1, 10, 5, 0.34)",
    },
  },
  sunset: {
    preview: "linear-gradient(180deg, #fffaf6 0%, #ffffff 52%)",
    light: {
      colorPrimary: "#ef7060",
      colorBgBase: "#fffaf6",
      colorTextBase: "#1f1a17",
      background:
        "linear-gradient(180deg, #fffaf6 0%, #ffffff 52%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(239, 112, 96, 0.12), transparent 28%), radial-gradient(circle at 100% 18%, rgba(242, 139, 124, 0.12), transparent 22%), linear-gradient(180deg, #fffaf6 0%, #ffffff 52%)",
      panelBackground: "rgba(255, 255, 255, 0.82)",
      headerBackground: "rgba(255, 249, 245, 0.82)",
      headerBorder: "rgba(239, 112, 96, 0.08)",
      borderColor: "rgba(239, 112, 96, 0.14)",
      borderSoftColor: "rgba(239, 112, 96, 0.08)",
      shadowColor: "rgba(239, 112, 96, 0.12)",
      assistantBubble: "rgba(255, 253, 252, 0.98)",
      senderBackground: "rgba(255, 255, 255, 0.94)",
      promptBackground: "rgba(255, 255, 255, 0.8)",
      promptHoverBackground: "#fff4ee",
      conversationHover: "rgba(239, 112, 96, 0.08)",
      conversationActive: "rgba(239, 112, 96, 0.14)",
      scrollThumb: "rgba(239, 112, 96, 0.28)",
      themePickerAccent: "#ef7060",
      assistantText: "#1f1a17",
      assistantHeading: "#231815",
      assistantLink: "#ef7060",
      assistantSurface: "linear-gradient(180deg, #fffdfc 0%, #fff7f4 100%)",
      assistantBorder: "#f3ddd7",
      assistantShadow: "0 18px 38px rgba(239, 112, 96, 0.12)",
      assistantRadius: "20px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        'Optima-Regular, Optima, PingFangSC-light, PingFangTC-light, "PingFang SC", Cambria, Cochin, Georgia, Times, "Times New Roman", serif',
      assistantH1Border: "rgba(239, 112, 96, 0.16)",
      assistantH2Bg: "linear-gradient(135deg, #ef7060 0%, #f28b7c 100%)",
      assistantH2Text: "#fff",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 10px 22px rgba(239, 112, 96, 0.2)",
      assistantH3Accent: "#ef7060",
      assistantH3Glow: "0 0 0 6px rgba(239, 112, 96, 0.12)",
      assistantH4Text: "#9c5147",
      assistantStrongBg: "rgba(239, 112, 96, 0.12)",
      assistantStrongText: "#a64b3e",
      assistantEmphasis: "#cf5f50",
      assistantMarker: "#ef7060",
      assistantMarkBg: "rgba(239, 112, 96, 0.18)",
      assistantMarkText: "#6e2b21",
      assistantBlockquoteBg: "#fff9f9",
      assistantQuoteBorder: "#ef7060",
      assistantInlineCodeBg: "rgba(239, 112, 96, 0.08)",
      assistantInlineCodeBorder: "rgba(239, 112, 96, 0.12)",
      assistantCodeBg: "#282c34",
      assistantCodeHeader: "#1f232b",
      assistantCodeText: "#f7f3f0",
      assistantTableBg: "#fff",
      assistantTableHeadBg: "#f7ebe7",
      assistantTableHeadText: "#4a2b25",
      assistantTableBorder: "#ead6cf",
      assistantHr: "rgba(239, 112, 96, 0.2)",
      assistantImageShadow: "0 10px 28px rgba(239, 112, 96, 0.12)",
    },
    dark: {
      colorPrimary: "#ff9b77",
      colorBgBase: "#1c120f",
      colorTextBase: "#fff3ed",
      background:
        "radial-gradient(circle at top left, rgba(255, 155, 119, 0.18), transparent 30%), linear-gradient(180deg, #170d0b 0%, #20110e 100%)",
      shellBackground:
        "radial-gradient(circle at 0% 0%, rgba(255, 155, 119, 0.2), transparent 26%), radial-gradient(circle at 100% 16%, rgba(239, 112, 96, 0.16), transparent 22%), linear-gradient(180deg, #120907 0%, #1b100d 100%)",
      panelBackground: "#24140f",
      headerBackground: "#1d100c",
      headerBorder: "#6a4034",
      borderColor: "#6f4336",
      borderSoftColor: "#543227",
      shadowColor: "rgba(14, 5, 4, 0.44)",
      assistantBubble: "#2a1813",
      senderBackground: "#24140f",
      promptBackground: "#311c17",
      promptHoverBackground: "#43251d",
      conversationHover: "#2c1914",
      conversationActive: "#45261d",
      scrollThumb: "rgba(255, 155, 119, 0.28)",
      themePickerAccent: "#ff9b77",
      assistantText: "#fff1ec",
      assistantHeading: "#fffaf7",
      assistantLink: "#ffb397",
      assistantSurface: "linear-gradient(180deg, #311d17 0%, #24140f 100%)",
      assistantBorder: "#6f4336",
      assistantShadow: "0 24px 50px rgba(14, 5, 4, 0.38)",
      assistantRadius: "20px",
      assistantPadding: "20px 24px",
      assistantBackdropFilter: "none",
      assistantFontFamily:
        'Optima-Regular, Optima, "PingFang SC", Cambria, Cochin, Georgia, serif',
      assistantH1Border: "#7b4b3e",
      assistantH2Bg: "linear-gradient(135deg, #d86f5d 0%, #ee8a73 100%)",
      assistantH2Text: "#fff9f6",
      assistantH2Border: "transparent",
      assistantH2Shadow: "0 12px 26px rgba(14, 5, 4, 0.28)",
      assistantH3Accent: "#ff9b77",
      assistantH3Glow: "0 0 0 6px rgba(255, 155, 119, 0.14)",
      assistantH4Text: "#ffc0a8",
      assistantStrongBg: "#3c221c",
      assistantStrongText: "#fff7f3",
      assistantEmphasis: "#ffc3ad",
      assistantMarker: "#ffad8d",
      assistantMarkBg: "#492920",
      assistantMarkText: "#fff7f3",
      assistantBlockquoteBg: "#35201a",
      assistantQuoteBorder: "#ff9b77",
      assistantInlineCodeBg: "#38211a",
      assistantInlineCodeBorder: "#6f4336",
      assistantCodeBg: "#191317",
      assistantCodeHeader: "#141014",
      assistantCodeText: "#fff1ec",
      assistantTableBg: "#2a1813",
      assistantTableHeadBg: "#43251d",
      assistantTableHeadText: "#fff1ec",
      assistantTableBorder: "#6f4336",
      assistantHr: "#6f4336",
      assistantImageShadow: "0 14px 34px rgba(14, 5, 4, 0.34)",
    },
  },
};

export const CHAT_THEME_KEYS = Object.keys(CHAT_THEMES) as ChatThemeKey[];

export function isChatThemeKey(value: unknown): value is ChatThemeKey {
  return (
    typeof value === "string" && CHAT_THEME_KEYS.includes(value as ChatThemeKey)
  );
}

export function getStoredChatTheme(): ChatThemeKey {
  if (typeof window === "undefined") return DEFAULT_CHAT_THEME;

  try {
    const stored = window.localStorage.getItem(CHAT_THEME_STORAGE_KEY);
    return isChatThemeKey(stored) ? stored : DEFAULT_CHAT_THEME;
  } catch {
    return DEFAULT_CHAT_THEME;
  }
}

export function persistChatTheme(theme: ChatThemeKey) {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(CHAT_THEME_STORAGE_KEY, theme);
  } catch {
    // ignore storage failures
  }
}

export function getChatTheme(theme: ChatThemeKey, isDark: boolean) {
  const definition = CHAT_THEMES[theme] ?? CHAT_THEMES[DEFAULT_CHAT_THEME];

  return {
    key: theme,
    preview: definition.preview,
    palette: isDark ? definition.dark : definition.light,
  };
}
