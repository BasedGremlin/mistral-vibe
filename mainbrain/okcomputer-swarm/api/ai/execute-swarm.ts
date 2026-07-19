import type {
  AgentContribution,
  SwarmExecutionInput,
  SwarmExecutionResult,
} from "./contracts";
import { SwarmStateMachine } from "./state-machine";
import { getProviderStatus } from "./provider-status";
import {
  runOpenAIPlanner,
  runOpenAISynthesizer,
  runOpenAIValidator,
  runOpenAIWorkers,
  selectOpenAIWorkerRoles,
} from "./openai-swarm";
import { runClaudeCritic } from "./claude-critic";
import {
  appendControlEvent,
  completeControlRun,
  createControlRun,
  writeCheckpoint,
} from "./supabase-control";

export async function executeSwarmRun(
  input: SwarmExecutionInput,
): Promise<SwarmExecutionResult> {
  const machine = new SwarmStateMachine();
  const providerStatus = getProviderStatus();
  const contributions: AgentContribution[] = [];
  let controlRunId: string | undefined;

  try {
    controlRunId = await createControlRun({
      externalSwarmId: input.externalSwarmId,
      ownerRef: input.ownerRef,
      query: input.query,
      providerStatus,
    });

    await appendControlEvent({
      runId: controlRunId,
      eventType: "run_created",
      state: machine.state,
      payload: { externalSwarmId: input.externalSwarmId, providers: providerStatus },
    });

    machine.transition("PLAN");
    await appendControlEvent({
      runId: controlRunId,
      eventType: "planning_started",
      state: machine.state,
    });
    const plan = await runOpenAIPlanner({
      query: input.query,
      priorContext: input.priorContext,
    });
    contributions.push(plan);
    await writeCheckpoint({
      runId: controlRunId,
      agentSlug: "planner",
      sequenceNo: 1,
      snapshot: { plan: plan.content },
    });

    machine.transition("ROUTE");
    const selectedRoles = await selectOpenAIWorkerRoles(input.query);
    await appendControlEvent({
      runId: controlRunId,
      eventType: "roles_selected",
      state: machine.state,
      payload: { selectedRoles },
    });

    machine.transition("EXECUTE");
    const workers = await runOpenAIWorkers({
      query: input.query,
      plan,
      selectedRoles,
      priorContext: input.priorContext,
    });
    for (const worker of workers) {
      contributions.push(worker);
      await appendControlEvent({
        runId: controlRunId,
        eventType: "agent_completed",
        state: machine.state,
        agentSlug: worker.slug,
        payload: { provider: worker.provider, latencyMs: worker.latencyMs },
      });
      await writeCheckpoint({
        runId: controlRunId,
        agentSlug: worker.slug,
        sequenceNo: 1,
        snapshot: { content: worker.content },
      });
    }

    machine.transition("CRITIQUE");
    const draftForCritique = [
      plan.content,
      ...workers.map((worker) => worker.content),
    ].join("\n\n");
    const claude = await runClaudeCritic(input.query, draftForCritique);
    const claudeCritique = claude.critique;
    if (claudeCritique) {
      contributions.push({
        slug: "claude-critic",
        provider: "anthropic",
        phase: "CRITIQUE",
        latencyMs: claude.latencyMs ?? 0,
        content: claudeCritique,
      });
    }
    await appendControlEvent({
      runId: controlRunId,
      eventType: claude.configured
        ? claude.error
          ? "claude_critic_failed"
          : "claude_critic_completed"
        : "claude_critic_unconfigured",
      state: machine.state,
      agentSlug: "claude-critic",
      payload: { model: claude.model, error: claude.error, latencyMs: claude.latencyMs },
    });

    machine.transition("VALIDATE");
    const validator = await runOpenAIValidator({
      query: input.query,
      plan,
      workers,
      externalCritique: claudeCritique,
    });
    contributions.push(validator);
    await appendControlEvent({
      runId: controlRunId,
      eventType: "validation_completed",
      state: machine.state,
      agentSlug: "validator",
      payload: { latencyMs: validator.latencyMs },
    });

    machine.transition("PERSIST");
    const synthesizer = await runOpenAISynthesizer({
      query: input.query,
      plan,
      workers,
      validator,
      externalCritique: claudeCritique,
    });
    contributions.push(synthesizer);
    await writeCheckpoint({
      runId: controlRunId,
      agentSlug: "synthesizer",
      sequenceNo: 1,
      snapshot: { finalOutput: synthesizer.content, validation: validator.content },
    });

    machine.transition("COMPLETE");
    await appendControlEvent({
      runId: controlRunId,
      eventType: "run_completed",
      state: machine.state,
      agentSlug: "synthesizer",
      payload: { contributionCount: contributions.length },
    });
    await completeControlRun({
      runId: controlRunId,
      finalSummary: synthesizer.content.slice(0, 4000),
    });

    return {
      finalOutput: synthesizer.content,
      validationSummary: validator.content,
      contributions,
      selectedRoles,
      providerStatus,
      controlRunId,
      claudeCritique,
    };
  } catch (error) {
    machine.fail();
    const message = error instanceof Error ? error.message : String(error);
    try {
      await appendControlEvent({
        runId: controlRunId,
        eventType: "run_failed",
        state: machine.state,
        payload: { error: message },
      });
      await completeControlRun({
        runId: controlRunId,
        failed: true,
        errorCode: message.slice(0, 500),
      });
    } catch (controlError) {
      console.error("Failed to persist swarm failure state", controlError);
    }
    throw error;
  }
}
