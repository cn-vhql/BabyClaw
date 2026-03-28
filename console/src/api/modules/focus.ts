import { request } from "../request";
import type {
  FocusNote,
  FocusRunResult,
  FocusSettings,
} from "../types/focus";

export const focusApi = {
  getFocusSettings: () => request<FocusSettings>("/focus/settings"),

  updateFocusSettings: (body: FocusSettings) =>
    request<FocusSettings>("/focus/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  runFocusNow: () =>
    request<FocusRunResult>("/focus/run", {
      method: "POST",
    }),

  listFocusNotes: (limit: number = 200) =>
    request<{ notes: FocusNote[] }>(`/focus/notes?limit=${limit}`),
};
