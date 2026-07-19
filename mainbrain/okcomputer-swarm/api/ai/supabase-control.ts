import { createHash } from "node:crypto";
import { createClient } from "@supabase/supabase-js";
import type { ProviderStatus, SwarmState } from "./contracts";

let client: ReturnType<typeof createClient> | undefined;

function getClient(): ReturnType<typeof createClient> | undefined {
  const url = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !serviceRoleKey) return undefined;
  if (client) return client;

  client = createClient(url, serviceRoleKey, {
    auth: {
      persistSession: false,
      autoRefreshToken: false,
      detectSessionInUrl: false,
    },
  });
  return client;
}

export async function createControlRun(input: {
  externalSwarmId?: number;
  ownerRef?: string;
  query: string;
  providerStatus: ProviderStatus;
}): Promise<string | undefined> {
  const supabase = getClient();
  if (!supabase) return undefined;

  const { data, error } = await supabase.rpc("swarm_create_run", {
    p_external_swarm_id: input.externalSwarmId ?? null,
    p_owner_ref: input.ownerRef ?? null,
    p_query: input.query,
    p_provider_plan: input.providerStatus,
  });

  if (error) throw new Error(`Supabase createControlRun: ${error.message}`);
  return typeof data === "string" ? data : undefined;
}

export async function appendControlEvent(input: {
  runId?: string;
  eventType: string;
  state: SwarmState;
  agentSlug?: string;
  payload?: Record<string, unknown>;
}): Promise<void> {
  const supabase = getClient();
  if (!supabase || !input.runId) return;

  const { error } = await supabase.rpc("swarm_append_event", {
    p_run_id: input.runId,
    p_event_type: input.eventType,
    p_state: input.state,
    p_agent_slug: input.agentSlug ?? null,
    p_payload: input.payload ?? {},
  });

  if (error) throw new Error(`Supabase appendControlEvent: ${error.message}`);
}

export async function writeCheckpoint(input: {
  runId?: string;
  agentSlug: string;
  sequenceNo: number;
  snapshot: Record<string, unknown>;
}): Promise<void> {
  const supabase = getClient();
  if (!supabase || !input.runId) return;

  const serialized = JSON.stringify(input.snapshot);
  const checksum = createHash("sha256").update(serialized).digest("hex");
  const { error } = await supabase.rpc("swarm_write_checkpoint", {
    p_run_id: input.runId,
    p_agent_slug: input.agentSlug,
    p_sequence_no: input.sequenceNo,
    p_checksum: checksum,
    p_snapshot: input.snapshot,
  });

  if (error) throw new Error(`Supabase writeCheckpoint: ${error.message}`);
}

export async function completeControlRun(input: {
  runId?: string;
  finalSummary?: string;
  failed?: boolean;
  errorCode?: string;
}): Promise<void> {
  const supabase = getClient();
  if (!supabase || !input.runId) return;

  const { error } = await supabase.rpc("swarm_complete_run", {
    p_run_id: input.runId,
    p_final_summary: input.finalSummary ?? null,
    p_failed: Boolean(input.failed),
    p_error_code: input.errorCode ?? null,
  });

  if (error) throw new Error(`Supabase completeControlRun: ${error.message}`);
}
