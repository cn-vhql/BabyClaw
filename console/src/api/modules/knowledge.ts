import { request } from "../request";

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  storage_type: string;
  created_at: string;
  document_count: number;
}

export interface KnowledgeBaseDetail extends KnowledgeBase {
  chunk_config: {
    chunk_type: string;
    max_length: number;
    overlap: number;
    separators: string[];
  };
  documents: Document[];
}

export interface Document {
  doc_id: string;
  filename: string;
  file_type: string;
  size: number;
  uploaded_at: string;
  chunk_count: number;
  chunks: Chunk[];
}

export interface Chunk {
  chunk_id: string;
  content: string;
  chunk_index: number;
  start?: number;
  end?: number;
  separator?: string;
}

export interface SearchResult {
  doc_id: string;
  filename: string;
  chunk_id: string;
  content: string;
  score: number;
}

export const knowledgeApi = {
  list: () =>
    request<{ knowledge_bases: KnowledgeBase[] }>("/knowledge/list"),

  create: (data: { name: string; description: string; storage_type: string }) =>
    request<{ id: string; name: string }>("/knowledge/create", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  delete: (kbId: string) =>
    request<{ deleted: boolean }>(`/knowledge/${kbId}`, {
      method: "DELETE",
    }),

  getDetail: (kbId: string) =>
    request<KnowledgeBaseDetail>(`/knowledge/${kbId}/detail`),

  uploadDocument: (
    kbId: string,
    file: File,
    chunkConfig?: {
      chunk_type: string;
      max_length: number;
      overlap: number;
    },
  ) => {
    const formData = new FormData();
    formData.append("file", file);

    if (chunkConfig) {
      formData.append("chunk_type", chunkConfig.chunk_type);
      formData.append("max_length", String(chunkConfig.max_length));
      formData.append("overlap", String(chunkConfig.overlap));
    }

    return request<{ doc_id: string; filename: string; chunk_count: number }>(
      `/knowledge/${kbId}/upload`,
      {
        method: "POST",
        body: formData,
        headers: {}, // Let browser set Content-Type for FormData
      },
    );
  },

  deleteDocument: (kbId: string, docId: string) =>
    request<{ deleted: boolean }>(`/knowledge/${kbId}/documents/${docId}`, {
      method: "DELETE",
    }),

  getChunks: (kbId: string, docId: string) =>
    request<{ chunks: Chunk[] }>(`/knowledge/${kbId}/documents/${docId}/chunks`),

  updateChunk: (kbId: string, docId: string, chunkId: string, content: string) =>
    request<{ updated: boolean }>(`/knowledge/${kbId}/documents/${docId}/chunks/${chunkId}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),

  saveChunks: (kbId: string, docId: string) =>
    request<{ updated: boolean; embedding_count: number }>(
      `/knowledge/${kbId}/documents/${docId}/chunks/save`,
      {
        method: "POST",
        body: JSON.stringify({}),
      }
    ),

  addChunk: (kbId: string, docId: string, content: string) =>
    request<{ added: boolean; chunk_id: string }>(`/knowledge/${kbId}/documents/${docId}/chunks`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  deleteChunk: (kbId: string, docId: string, chunkId: string) =>
    request<{ deleted: boolean }>(`/knowledge/${kbId}/documents/${docId}/chunks/${chunkId}`, {
      method: "DELETE",
    }),

  search: (kbId: string, query: string, topK: number = 5) =>
    request<{ results: SearchResult[]; query: string }>(`/knowledge/${kbId}/search`, {
      method: "POST",
      body: JSON.stringify({ query, top_k: topK }),
    }),
};
