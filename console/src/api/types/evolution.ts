/**
 * Evolution types for digital life evolution system
 */

export type EvolutionTriggerType = "manual" | "cron" | "auto";
export type EvolutionStatus =
  | "running"
  | "success"
  | "failed"
  | "cancelled"
  | "reverted";

export interface EvolutionConfig {
  enabled: boolean;
  auto_evolution: boolean;
  max_generations: number | null;  // null or 0 means unlimited
  archive_enabled: boolean;
}

export interface EvolutionRecord {
  id: string;
  generation: number;
  agent_id: string;
  agent_name: string;
  timestamp: string;
  trigger_type: EvolutionTriggerType;
  status: EvolutionStatus;
  is_active: boolean;
  archive_id?: string;
  reverted_to_record_id?: string;
  error_message?: string;
  tool_calls_count: number;
  tools_used: string[];
  output_summary: string;
  duration_seconds?: number;
  tokens_used?: number;
}

export interface EvolutionArchive {
  archive_id: string;
  evolution_id: string;
  generation: number;
  timestamp: string;
  before_files: Record<string, string>;
  after_files: Record<string, string>;
  changed_files: string[];
  tool_execution_log: Array<{
    tool?: string;
    call_id?: string;
    args?: unknown;
    result?: unknown;
    timestamp?: string;
  }>;
  structured_records: Array<{
    type?: string;
    source?: string;
    timestamp?: string;
    data?: unknown;
  }>;
  full_output: string;
  memory_snapshot?: Record<string, unknown>;
  reverted_to_record_id?: string;
}

export interface EvolutionRollbackResult {
  active_record_id: string;
  reverted_record: EvolutionRecord;
  active_record: EvolutionRecord;
}

export interface EvolutionRunRequest {
  trigger_type?: EvolutionTriggerType;
  custom_prompt?: string;
  timeout_seconds?: number;
}
