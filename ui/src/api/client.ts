export interface ProjectSummary {
  project_id: string;
  features: number;
  states: string[];
}

export interface FeatureSummary {
  feature_id: string;
  title: string;
  current_state: string;
  pull_request: number | null;
  coverage: number | null;
  unit_test_status: string;
  functional_test_status: string;
  deployment_environment: string | null;
  evidence_count: number;
}

export interface ProjectOverview {
  project_id: string;
  features: FeatureSummary[];
  executions: number;
  failed_executions: number;
}

export interface TimelineEntry {
  from_state: string;
  to_state: string;
  agent: string;
  timestamp: string;
  retry_number: number;
  human_intervention: boolean;
  execution_id: string | null;
  skill: string | null;
  duration_seconds: number | null;
  evidence_refs: string[];
}

export interface FactoryEvent {
  event_id: string;
  event_type: string;
  timestamp: string;
  project_id: string | null;
  feature_id: string | null;
  execution_id: string | null;
  stage: string | null;
  agent: string | null;
  skill: string | null;
  status: string | null;
  evidence_refs: string[];
}

export interface EngineeringMetrics {
  projects: number;
  features_total: number;
  features_completed: number;
  features_by_state: Record<string, number>;
  autonomous_completion_pct: number | null;
  ac_to_test_coverage_pct: number | null;
  pr_first_pass_pct: number | null;
  self_heal_success_pct: number | null;
  failures_by_class: Record<string, number>;
  executions_total: number;
  executions_failed: number;
  retries_total: number;
  human_interventions: number;
}

export interface QualityCheck {
  name: string;
  threshold: string;
  actual: string;
  passed: boolean;
  evidence_ref: string;
}

export interface QualityView {
  merge_decision: {
    decision: string;
    checks: QualityCheck[];
  } | null;
  validation_report: {
    decision: string;
    mandatory_ac_pass_percentage: number;
    threshold: number;
    results: {
      ac_id: string;
      story_id: string;
      mandatory: boolean;
      test_outcome: string;
      passed: boolean;
    }[];
  } | null;
}

export interface Episode {
  episode_id: string;
  stage: string;
  failure_class: string;
  signature: string;
  repair_action: string;
  outcome: string;
  attempt: number;
}

export interface HealingView {
  episodes: Episode[];
  promotions: Record<string, unknown>[];
  learning_record: Record<string, unknown> | null;
}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText} for ${path}`);
  }
  return (await response.json()) as T;
}

export const api = {
  projects: () => get<ProjectSummary[]>("/api/v1/projects"),
  overview: (projectId: string) =>
    get<ProjectOverview>(`/api/v1/projects/${projectId}/overview`),
  timeline: (projectId: string, featureId: string) =>
    get<TimelineEntry[]>(
      `/api/v1/projects/${projectId}/features/${featureId}/timeline`,
    ),
  events: (projectId: string) =>
    get<FactoryEvent[]>(`/api/v1/projects/${projectId}/events`),
  metrics: () => get<EngineeringMetrics>("/api/v1/metrics/engineering"),
  quality: (projectId: string) =>
    get<QualityView>(`/api/v1/projects/${projectId}/quality`),
  healing: (projectId: string) =>
    get<HealingView>(`/api/v1/projects/${projectId}/healing`),
};
