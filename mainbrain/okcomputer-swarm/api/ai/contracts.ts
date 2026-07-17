export const SWARM_STATES = [
  "INTAKE",
  "PLAN",
  "ROUTE",
  "EXECUTE",
  "CRITIQUE",
  "VALIDATE",
  "PERSIST",
  "COMPLETE",
  "FAILED",
] as const;

export type SwarmState = (typeof SWARM_STATES)[number];

export type ProviderName = "openai" | "anthropic" | "huggingface-local";

export type AgentContribution = {
  slug: string;
  content: string;
  provider: ProviderName;
  phase: SwarmState;
  latencyMs: number;
};

export type ProviderStatus = {
  openai: {
    configured: boolean;
    model: string;
  };
  anthropic: {
    configured: boolean;
    model: string;
    mode: "openai-sdk-compatibility";
  };
  huggingface: {
    enabled: boolean;
    model: string;
    localModelPath: string;
    remoteModelsAllowed: boolean;
  };
  supabase: {
    configured: boolean;
    projectRef: string;
    role: "control-plane-only";
  };
};

export type SwarmExecutionInput = {
  query: string;
  externalSwarmId?: number;
  ownerRef?: string;
  priorContext?: string;
};

export type SwarmExecutionResult = {
  finalOutput: string;
  contributions: AgentContribution[];
  selectedRoles: string[];
  providerStatus: ProviderStatus;
  controlRunId?: string;
  validationSummary: string;
  claudeCritique?: string;
};
