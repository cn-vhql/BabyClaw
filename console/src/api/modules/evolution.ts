import { request } from "../request";
import type {
  EvolutionConfig,
  EvolutionRecord,
  EvolutionArchive,
  EvolutionRollbackResult,
  EvolutionRunRequest,
} from "../types/evolution";

export const evolutionApi = {
  getConfig: () =>
    request<EvolutionConfig>("/evolution/config"),

  updateConfig: (config: EvolutionConfig) =>
    request<EvolutionConfig>("/evolution/config", {
      method: "PUT",
      body: JSON.stringify(config),
    }),

  listRecords: (limit: number = 50) =>
    request<EvolutionRecord[]>(`/evolution/records?limit=${limit}`),

  getRecord: (recordId: string) =>
    request<EvolutionRecord>(`/evolution/records/${recordId}`),

  getArchiveByRecord: (recordId: string) =>
    request<EvolutionArchive>(`/evolution/records/${recordId}/archive`),

  getArchive: (archiveId: string) =>
    request<EvolutionArchive>(`/evolution/archives/${archiveId}`),

  runEvolution: (req: EvolutionRunRequest) =>
    request<EvolutionRecord>("/evolution/run", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  cancelRecord: (recordId: string) =>
    request<EvolutionRecord>(`/evolution/records/${recordId}/cancel`, {
      method: "POST",
    }),

  rollbackRecord: (recordId: string) =>
    request<EvolutionRollbackResult>(`/evolution/records/${recordId}/rollback`, {
      method: "POST",
    }),

  getArchiveFile: (archiveId: string, filename: string) =>
    request<{ filename: string; content: string }>(
      `/evolution/archives/${archiveId}/files/${filename}`
    ),

  deleteRecord: (recordId: string) =>
    request<{ message: string }>(`/evolution/records/${recordId}`, {
      method: "DELETE",
    }),
};
