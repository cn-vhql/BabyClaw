/**
 * Evolution types for digital life evolution system
 */

export type EvolutionTriggerType = "manual" | "cron" | "auto";
export type EvolutionStatus = "running" | "success" | "failed" | "cancelled";

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

  soul_before?: string;
  soul_after?: string;
  profile_before?: string;
  profile_after?: string;
  plan_before?: string;
  plan_after?: string;

  status: EvolutionStatus;
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
  files: Record<string, string>;
  tool_execution_log: Array<{
    tool: string;
    args?: any;
    result?: any;
    timestamp: string;
  }>;
  full_output: string;
  memory_snapshot?: Record<string, any>;
}

export interface EvolutionRunRequest {
  trigger_type?: EvolutionTriggerType;
  custom_prompt?: string;
  max_iterations?: number;
  timeout_seconds?: number;
}
