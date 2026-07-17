import { Agent, run, tool } from "@openai/agents";
import { z } from "zod";
import type { AgentContribution } from "./contracts";
import { MASTERZIP_CONTEXT, ROLE_INSTRUCTIONS } from "./project-context";
import { rankRolesByKeywords, rankRolesLocally } from "./hf-local-router";

const model = process.env.OPENAI_MODEL ?? "gpt-5.4";

const projectStateTool = tool({
  name: "get_project_validation_state",
  description:
    "Return the canonical MASTERZIP project state, validation gate, and non-negotiable controls.",
  parameters: z.object({ reason: z.string().min(1).max(300) }),
  async execute() {
    return MASTERZIP_CONTEXT;
  },
});

const approvalGateTool = tool({
  name: "classify_action_gate",
  description:
    "Classify a proposed action as analysis-only, reversible write, external side effect, physical build, or sale/compliance action.",
  parameters: z.object({ action: z.string().min(1).max(500) }),
  async execute({ action }: { action: string }) {
    const lower = action.toLowerCase();
    if (/(sell|sale|certif|deploy outdoor|power tool|cut|drill|weld)/.test(lower)) {
      return {
        gate: "HUMAN_APPROVAL_AND_EVIDENCE_REQUIRED",
        reason:
          "Physical, sale, or compliance-affecting actions cannot be auto-approved.",
      };
    }
    if (/(send|publish|delete|purchase|pay|merge|deploy)/.test(lower)) {
      return {
        gate: "HUMAN_APPROVAL_REQUIRED",
        reason: "External or destructive side effect.",
      };
    }
    return { gate: "ANALYSIS_ALLOWED", reason: "Read-only planning or reversible draft." };
  },
});

function assertOpenAIConfigured(): void {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error(
      "OPENAI_API_KEY is not configured. Use the secure OpenAI Platform setup flow, then place the key in the server environment.",
    );
  }
}

function createAgent(slug: string): Agent {
  return new Agent({
    name: slug.charAt(0).toUpperCase() + slug.slice(1),
    model,
    instructions: [
      ROLE_INSTRUCTIONS[slug] ?? ROLE_INSTRUCTIONS.synthesizer,
      "Never claim that code ran, a connector succeeded, a physical test passed, or evidence exists unless supplied context proves it.",
      "Do not output private chain-of-thought. Return decisions, evidence, assumptions, uncertainties, and concise verification notes.",
      MASTERZIP_CONTEXT,
    ].join("\n\n"),
    tools:
      slug === "planner" || slug === "validator"
        ? [projectStateTool, approvalGateTool]
        : [projectStateTool],
  });
}

function outputText(value: unknown): string {
  if (typeof value === "string") return value.trim();
  if (value === null || value === undefined) return "";
  return JSON.stringify(value, null, 2);
}

async function executeAgent(
  slug: string,
  prompt: string,
  phase: AgentContribution["phase"],
): Promise<AgentContribution> {
  assertOpenAIConfigured();
  const startedAt = Date.now();
  const result = await run(createAgent(slug), prompt);
  return {
    slug,
    provider: "openai",
    phase,
    latencyMs: Date.now() - startedAt,
    content: outputText(result.finalOutput),
  };
}

export async function runOpenAIPlanner(input: {
  query: string;
  priorContext?: string;
}): Promise<AgentContribution> {
  return executeAgent(
    "planner",
    [
      "Create the smallest complete execution plan for this request.",
      "Use explicit states and approval gates.",
      "REQUEST:",
      input.query,
      input.priorContext ? `PRIOR CONTEXT:\n${input.priorContext}` : "",
    ]
      .filter(Boolean)
      .join("\n\n"),
    "PLAN",
  );
}

export async function selectOpenAIWorkerRoles(
  query: string,
): Promise<string[]> {
  const workerLimit = Math.max(
    1,
    Math.min(4, Number(process.env.OPENAI_SWARM_MAX_WORKERS ?? "3")),
  );
  const semanticRoles = await rankRolesLocally(query, workerLimit);
  const fallbackRoles = rankRolesByKeywords(query, workerLimit);
  const selected = (semanticRoles ?? fallbackRoles)
    .map((entry) => entry.slug)
    .filter((slug) => !["planner", "validator", "synthesizer"].includes(slug));

  return selected.length > 0 ? selected : ["coder", "analyst"];
}

export async function runOpenAIWorkers(input: {
  query: string;
  plan: AgentContribution;
  selectedRoles: string[];
  priorContext?: string;
}): Promise<AgentContribution[]> {
  return Promise.all(
    input.selectedRoles.map((slug) =>
      executeAgent(
        slug,
        [
          `You own the ${slug} workstream.`,
          "Produce a bounded contribution that the validator can audit.",
          "REQUEST:",
          input.query,
          "PLAN:",
          input.plan.content,
          input.priorContext ? `PRIOR CONTEXT:\n${input.priorContext}` : "",
        ]
          .filter(Boolean)
          .join("\n\n"),
        "EXECUTE",
      ),
    ),
  );
}

export async function runOpenAIValidator(input: {
  query: string;
  plan: AgentContribution;
  workers: AgentContribution[];
  externalCritique?: string;
}): Promise<AgentContribution> {
  const combinedWorkers = input.workers
    .map((worker) => `### ${worker.slug}\n${worker.content}`)
    .join("\n\n");

  return executeAgent(
    "validator",
    [
      "Audit the plan, worker outputs, and any cross-provider critique.",
      "List blocking defects first. Mark unsupported claims and false completion signals.",
      "Return a concise verdict: ACCEPT, ACCEPT_WITH_BLOCKS, or REVISE.",
      "REQUEST:",
      input.query,
      "PLAN:",
      input.plan.content,
      "WORKER OUTPUTS:",
      combinedWorkers,
      input.externalCritique
        ? `EXTERNAL CLAUDE CRITIQUE:\n${input.externalCritique}`
        : "EXTERNAL CLAUDE CRITIQUE: not configured; do not treat this as a failure.",
    ].join("\n\n"),
    "VALIDATE",
  );
}

export async function runOpenAISynthesizer(input: {
  query: string;
  plan: AgentContribution;
  workers: AgentContribution[];
  validator: AgentContribution;
  externalCritique?: string;
}): Promise<AgentContribution> {
  const combinedWorkers = input.workers
    .map((worker) => `### ${worker.slug}\n${worker.content}`)
    .join("\n\n");

  return executeAgent(
    "synthesizer",
    [
      "Produce the final user-facing result.",
      "Lead with the five highest-signal decisions or changes.",
      "Preserve blockers, validation limits, and unresolved critic findings.",
      "End with the exact next executable action.",
      "REQUEST:",
      input.query,
      "PLAN:",
      input.plan.content,
      "WORKER OUTPUTS:",
      combinedWorkers,
      input.externalCritique
        ? `EXTERNAL CLAUDE CRITIQUE:\n${input.externalCritique}`
        : "EXTERNAL CLAUDE CRITIQUE: unavailable.",
      "VALIDATOR:",
      input.validator.content,
    ].join("\n\n"),
    "PERSIST",
  );
}
