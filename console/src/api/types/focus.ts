import type { ActiveHoursConfig } from "./heartbeat";

export interface FocusSettings {
  enabled: boolean;
  every: string;
  notificationChannel: string;
  doNotDisturb?: ActiveHoursConfig | null;
  tags: string[];
}

export interface FocusNote {
  id: string;
  title: string;
  content: string;
  tags: string[];
  source: string;
  createdAt: string;
  sessionId?: string | null;
  runId?: string | null;
}

export interface FocusRunResult {
  status: "completed" | "skipped" | "timed_out";
  reason?: string | null;
  noteCount: number;
  runId?: string | null;
}
