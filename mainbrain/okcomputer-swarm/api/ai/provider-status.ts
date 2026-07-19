import { homedir } from "node:os";
import path from "node:path";
import type { ProviderStatus } from "./contracts";

export function defaultHfRoot(): string {
  return process.env.HF_LOCAL_MODEL_PATH ??
    path.join(homedir(), "Desktop", "HuggingFaces");
}

export function getProviderStatus(): ProviderStatus {
  return {
    openai: {
      configured: Boolean(process.env.OPENAI_API_KEY),
      model: process.env.OPENAI_MODEL ?? "gpt-5.4",
    },
    anthropic: {
      configured: Boolean(process.env.ANTHROPIC_API_KEY),
      model: process.env.CLAUDE_MODEL ?? "claude-sonnet-4-6",
      mode: "openai-sdk-compatibility",
    },
    huggingface: {
      enabled: process.env.HF_LOCAL_ROUTER_ENABLED !== "false",
      model:
        process.env.HF_EMBEDDING_MODEL ??
        "mixedbread-ai/mxbai-embed-xsmall-v1",
      localModelPath: defaultHfRoot(),
      remoteModelsAllowed: process.env.HF_ALLOW_REMOTE_MODELS === "true",
    },
    supabase: {
      configured: Boolean(
        process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_ROLE_KEY,
      ),
      projectRef:
        process.env.SUPABASE_PROJECT_REF ?? "dxyghtyjndylvfugutsr",
      role: "control-plane-only",
    },
  };
}
