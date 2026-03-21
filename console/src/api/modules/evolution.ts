import { request } from "../request";
import type {
  EvolutionConfig,
  EvolutionRecord,
  EvolutionArchive,
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

  getArchive: (archiveId: string) =>
    request<EvolutionArchive>(`/evolution/archives/${archiveId}`),

  runEvolution: (req: EvolutionRunRequest) =>
    request<EvolutionRecord>("/evolution/run", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  getArchiveFile: (archiveId: string, filename: string) =>
    request<{ filename: string; content: string }>(
      `/evolution/archives/${archiveId}/files/${filename}`
    ),
};
