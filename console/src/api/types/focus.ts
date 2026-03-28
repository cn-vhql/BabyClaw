import type { ActiveHoursConfig } from "./heartbeat";

export interface FocusSettings {
  enabled: boolean;
  every: string;
  notificationChannel: string;
  doNotDisturb?: ActiveHoursConfig | null;
  tags: string[];
}

export interface FocusNoteSummary {
  id: string;
  title: string;
  previewText: string;
  tags: string[];
  source: string;
  createdAt: string;
  runId?: string | null;
}

export interface FocusNoteDetail extends FocusNoteSummary {
  content: string;
  sessionId?: string | null;
  fingerprint?: string | null;
}

export type FocusRunStatus =
  | "running"
  | "completed"
  | "skipped"
  | "timed_out"
  | "failed"
  | "cancelled";

export type FocusTriggerType = "manual" | "scheduled";

export interface FocusRunRecord {
  id: string;
  status: FocusRunStatus;
  reason?: string | null;
  triggerType: FocusTriggerType;
  startedAt: string;
  finishedAt?: string | null;
  noteCount: number;
  summary: string;
  notificationStatus: string;
  archiveId?: string | null;
  tagSnapshot: string[];
  sessionId?: string | null;
}

export interface FocusRunDetail extends FocusRunRecord {
  generatedNotes: FocusNoteSummary[];
}

export interface FocusRunArchive {
  runId: string;
  prompt: string;
  fullOutput: string;
  toolExecutionLog: Array<Record<string, unknown>>;
  noteIds: string[];
  tagSnapshot: string[];
  notificationResult: Record<string, unknown>;
  errorMessage?: string | null;
  createdAt: string;
}

export interface FocusNotesPage {
  items: FocusNoteSummary[];
  total: number;
  page: number;
  pageSize: number;
}

export interface FocusRunsPage {
  items: FocusRunRecord[];
  total: number;
  page: number;
  pageSize: number;
}
