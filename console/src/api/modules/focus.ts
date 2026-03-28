import { request } from "../request";
import type {
  FocusNoteDetail,
  FocusNotesPage,
  FocusRunArchive,
  FocusRunDetail,
  FocusRunRecord,
  FocusRunsPage,
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
    request<FocusRunRecord>("/focus/run", {
      method: "POST",
    }),

  cancelFocusRun: (runId: string) =>
    request<FocusRunRecord>(`/focus/runs/${runId}/cancel`, {
      method: "POST",
    }),

  listFocusNotes: (params?: {
    page?: number;
    pageSize?: number;
    q?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.pageSize) search.set("page_size", String(params.pageSize));
    if (params?.q) search.set("q", params.q);
    const suffix = search.toString();
    return request<FocusNotesPage>(
      `/focus/notes${suffix ? `?${suffix}` : ""}`,
    );
  },

  getFocusNote: (noteId: string) =>
    request<FocusNoteDetail>(`/focus/notes/${noteId}`),

  listFocusRuns: (params?: {
    page?: number;
    pageSize?: number;
    status?: string;
  }) => {
    const search = new URLSearchParams();
    if (params?.page) search.set("page", String(params.page));
    if (params?.pageSize) search.set("page_size", String(params.pageSize));
    if (params?.status) search.set("status", params.status);
    const suffix = search.toString();
    return request<FocusRunsPage>(
      `/focus/runs${suffix ? `?${suffix}` : ""}`,
    );
  },

  getFocusRun: (runId: string) => request<FocusRunDetail>(`/focus/runs/${runId}`),

  getFocusRunArchive: (runId: string) =>
    request<FocusRunArchive>(`/focus/runs/${runId}/archive`),
};
