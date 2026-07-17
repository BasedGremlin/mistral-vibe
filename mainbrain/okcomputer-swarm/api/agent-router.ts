import { z } from "zod";
import { createRouter, publicQuery, authedQuery } from "./middleware";
import { getDb } from "./queries/connection";
import { agents, swarms, swarmAgents, messages, tasks } from "@db/schema";
import { and, eq, desc, sql, inArray } from "drizzle-orm";
import { executeSwarmRun } from "./ai/execute-swarm";
import { getProviderStatus } from "./ai/provider-status";
import type { SwarmExecutionResult } from "./ai/contracts";

export const agentRouter = createRouter({
  list: publicQuery.query(async () => {
    const db = getDb();
    return db.select().from(agents).orderBy(agents.name);
  }),

  getBySlug: publicQuery
    .input(z.object({ slug: z.string() }))
    .query(async ({ input }) => {
      const db = getDb();
      const [agent] = await db
        .select()
        .from(agents)
        .where(eq(agents.slug, input.slug))
        .limit(1);
      return agent ?? null;
    }),

  providerStatus: authedQuery.query(() => getProviderStatus()),

  getStats: publicQuery.query(async () => {
    const db = getDb();
    const [agentStats] = await db
      .select({
        totalAgents: sql<number>`count(*)`,
        activeAgents: sql<number>`sum(case when ${agents.status} = 'active' then 1 else 0 end)`,
        totalTasks: sql<number>`sum(${agents.totalTasks})`,
        avgSuccessRate: sql<number>`avg(${agents.successRate})`,
      })
      .from(agents);
    return agentStats;
  }),

  orchestrate: authedQuery
    .input(z.object({ query: z.string().min(1).max(12000) }))
    .mutation(async ({ input, ctx }) => {
      const db = getDb();
      const userId = ctx.user.id;

      const allAgents = await db.select().from(agents);
      const selectedAgents = selectAgentsForQuery(input.query, allAgents);

      const [swarm] = await db
        .insert(swarms)
        .values({
          name: `Swarm: ${input.query.slice(0, 60)}`,
          query: input.query,
          status: "running",
          agentCount: selectedAgents.length,
          userId,
          metadata: {
            executionMode: "real-provider-run",
            createdBy: "openai-agents-sdk",
          },
        })
        .$returningId();

      const swarmId = Number(swarm.id);

      for (let i = 0; i < selectedAgents.length; i += 1) {
        const agent = selectedAgents[i];
        await db.insert(swarmAgents).values({
          swarmId,
          agentId: agent.id,
          role:
            agent.slug === "planner"
              ? "orchestrator"
              : agent.slug === "validator"
                ? "validator"
                : "worker",
          status: agent.slug === "planner" ? "active" : "waiting",
        });
      }

      await db.insert(messages).values({
        swarmId,
        role: "user",
        content: input.query,
      });

      try {
        const execution = await executeSwarmRun({
          query: input.query,
          externalSwarmId: swarmId,
          ownerRef: String(userId),
        });

        await persistExecution({
          swarmId,
          execution,
          allAgents,
        });

        return {
          swarmId,
          agents: selectedAgents,
          execution: {
            selectedRoles: execution.selectedRoles,
            providerStatus: execution.providerStatus,
            controlRunId: execution.controlRunId,
          },
        };
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown swarm error";

        await db.insert(messages).values({
          swarmId,
          role: "system",
          content: `Execution failed safely: ${message}`,
          reasoning: "Provider failure was persisted; no result was fabricated.",
        });

        await db
          .update(swarms)
          .set({
            status: "failed",
            summary: message,
            completedAt: new Date(),
            metadata: {
              executionMode: "real-provider-run",
              failure: message,
              providerStatus: getProviderStatus(),
            },
          })
          .where(eq(swarms.id, swarmId));

        throw new Error(message);
      }
    }),

  getSwarm: authedQuery
    .input(z.object({ id: z.number() }))
    .query(async ({ input, ctx }) => {
      const db = getDb();
      const [swarm] = await db
        .select()
        .from(swarms)
        .where(and(eq(swarms.id, input.id), eq(swarms.userId, ctx.user.id)))
        .limit(1);

      if (!swarm) return null;

      const swarmAgentList = await db
        .select()
        .from(swarmAgents)
        .where(eq(swarmAgents.swarmId, input.id));

      const agentIds = swarmAgentList.map((sa) => sa.agentId);
      const agentDetails =
        agentIds.length > 0
          ? await db.select().from(agents).where(inArray(agents.id, agentIds))
          : [];

      const messageList = await db
        .select()
        .from(messages)
        .where(eq(messages.swarmId, input.id))
        .orderBy(messages.createdAt);

      const taskList = await db
        .select()
        .from(tasks)
        .where(eq(tasks.swarmId, input.id))
        .orderBy(tasks.createdAt);

      return {
        ...swarm,
        agents: swarmAgentList.map((sa) => ({
          ...sa,
          agent: agentDetails.find((agent) => agent.id === sa.agentId),
        })),
        messages: messageList,
        tasks: taskList,
      };
    }),

  addMessage: authedQuery
    .input(
      z.object({
        swarmId: z.number(),
        agentId: z.number().optional(),
        role: z.enum(["user", "agent", "system"]),
        content: z.string().min(1).max(12000),
        sources: z
          .array(
            z.object({
              title: z.string(),
              url: z.string(),
              snippet: z.string(),
            }),
          )
          .optional(),
        reasoning: z.string().optional(),
        tokens: z.number().optional(),
        latency: z.number().optional(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const db = getDb();
      const [ownedSwarm] = await db
        .select()
        .from(swarms)
        .where(
          and(
            eq(swarms.id, input.swarmId),
            eq(swarms.userId, ctx.user.id),
          ),
        )
        .limit(1);
      if (!ownedSwarm) throw new Error("Swarm not found");

      const [msg] = await db
        .insert(messages)
        .values({
          swarmId: input.swarmId,
          agentId: input.agentId,
          role: input.role,
          content: input.content,
          sources: input.sources,
          reasoning: input.reasoning,
          tokens: input.tokens ?? 0,
          latency: input.latency ?? 0,
        })
        .$returningId();

      if (input.role !== "user") return { id: Number(msg.id) };

      const prior = await db
        .select()
        .from(messages)
        .where(eq(messages.swarmId, input.swarmId))
        .orderBy(desc(messages.createdAt))
        .limit(10);

      await db
        .update(swarms)
        .set({ status: "running", completedAt: null })
        .where(eq(swarms.id, input.swarmId));

      try {
        const execution = await executeSwarmRun({
          query: input.content,
          externalSwarmId: input.swarmId,
          ownerRef: String(ctx.user.id),
          priorContext: prior
            .reverse()
            .map((item) => `${item.role}: ${item.content}`)
            .join("\n")
            .slice(-12000),
        });
        const allAgents = await db.select().from(agents);
        await persistExecution({
          swarmId: input.swarmId,
          execution,
          allAgents,
        });
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Unknown follow-up error";
        await db.insert(messages).values({
          swarmId: input.swarmId,
          role: "system",
          content: `Follow-up failed safely: ${message}`,
        });
        await db
          .update(swarms)
          .set({
            status: "failed",
            summary: message,
            completedAt: new Date(),
          })
          .where(eq(swarms.id, input.swarmId));
      }

      return { id: Number(msg.id) };
    }),

  completeSwarm: authedQuery
    .input(
      z.object({
        swarmId: z.number(),
        summary: z.string(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const db = getDb();
      await db
        .update(swarms)
        .set({
          status: "completed",
          summary: input.summary,
          completedAt: new Date(),
        })
        .where(
          and(
            eq(swarms.id, input.swarmId),
            eq(swarms.userId, ctx.user.id),
          ),
        );
      return { ok: true };
    }),

  updateAgentStatus: authedQuery
    .input(
      z.object({
        swarmAgentId: z.number(),
        status: z.enum(["active", "completed", "failed", "waiting"]),
        contribution: z.string().optional(),
      }),
    )
    .mutation(async ({ input, ctx }) => {
      const db = getDb();
      const [membership] = await db
        .select()
        .from(swarmAgents)
        .where(eq(swarmAgents.id, input.swarmAgentId))
        .limit(1);
      if (!membership) throw new Error("Swarm agent not found");

      const [ownedSwarm] = await db
        .select()
        .from(swarms)
        .where(
          and(
            eq(swarms.id, membership.swarmId),
            eq(swarms.userId, ctx.user.id),
          ),
        )
        .limit(1);
      if (!ownedSwarm) throw new Error("Swarm agent not found");

      const update: Record<string, unknown> = { status: input.status };
      if (input.contribution) update.contribution = input.contribution;
      if (input.status === "completed" || input.status === "failed") {
        update.completedAt = new Date();
      }
      await db
        .update(swarmAgents)
        .set(update)
        .where(eq(swarmAgents.id, input.swarmAgentId));
      return { ok: true };
    }),

  listSwarms: authedQuery.query(async ({ ctx }) => {
    const db = getDb();
    return db
      .select()
      .from(swarms)
      .where(eq(swarms.userId, ctx.user.id))
      .orderBy(desc(swarms.createdAt));
  }),

  history: authedQuery.query(async ({ ctx }) => {
    const db = getDb();
    const swarmList = await db
      .select()
      .from(swarms)
      .where(
        and(
          eq(swarms.status, "completed"),
          eq(swarms.userId, ctx.user.id),
        ),
      )
      .orderBy(desc(swarms.createdAt))
      .limit(50);

    const result = [];
    for (const swarm of swarmList) {
      const swarmAgentList = await db
        .select()
        .from(swarmAgents)
        .where(eq(swarmAgents.swarmId, swarm.id));
      const agentIds = swarmAgentList.map((sa) => sa.agentId);
      const agentDetails =
        agentIds.length > 0
          ? await db.select().from(agents).where(inArray(agents.id, agentIds))
          : [];
      const messageList = await db
        .select()
        .from(messages)
        .where(eq(messages.swarmId, swarm.id))
        .orderBy(messages.createdAt);

      result.push({
        ...swarm,
        agents: agentDetails,
        messageCount: messageList.length,
      });
    }
    return result;
  }),
});

async function persistExecution(input: {
  swarmId: number;
  execution: SwarmExecutionResult;
  allAgents: Array<{
    id: number;
    slug: string;
  }>;
}) {
  const db = getDb();
  const requiredSlugs = new Set([
    "planner",
    "validator",
    "synthesizer",
    ...input.execution.selectedRoles,
  ]);

  for (const slug of requiredSlugs) {
    const agent = input.allAgents.find((candidate) => candidate.slug === slug);
    if (!agent) continue;
    const [existing] = await db
      .select()
      .from(swarmAgents)
      .where(
        and(
          eq(swarmAgents.swarmId, input.swarmId),
          eq(swarmAgents.agentId, agent.id),
        ),
      )
      .limit(1);
    if (!existing) {
      await db.insert(swarmAgents).values({
        swarmId: input.swarmId,
        agentId: agent.id,
        role:
          slug === "planner"
            ? "orchestrator"
            : slug === "validator"
              ? "validator"
              : "worker",
        status: "waiting",
      });
    }
  }

  for (const contribution of input.execution.contributions) {
    const matched =
      input.allAgents.find((agent) => agent.slug === contribution.slug) ??
      input.allAgents.find((agent) =>
        contribution.slug === "claude-critic"
          ? agent.slug === "validator"
          : agent.slug === "synthesizer",
      );

    await db.insert(messages).values({
      swarmId: input.swarmId,
      agentId: matched?.id,
      role: "agent",
      content:
        contribution.slug === "claude-critic"
          ? `[Claude critic]\n${contribution.content}`
          : contribution.content,
      reasoning: JSON.stringify({
        provider: contribution.provider,
        phase: contribution.phase,
        trace: "decision-summary-only",
      }),
      latency: contribution.latencyMs,
    });

    if (matched) {
      await db
        .update(swarmAgents)
        .set({
          status: "completed",
          contribution: contribution.content.slice(0, 4000),
          completedAt: new Date(),
        })
        .where(
          sql`${swarmAgents.swarmId} = ${input.swarmId} and ${swarmAgents.agentId} = ${matched.id}`,
        );
    }
  }

  await db
    .update(swarms)
    .set({
      status: "completed",
      summary: input.execution.finalOutput,
      completedAt: new Date(),
      metadata: {
        executionMode: "real-provider-run",
        selectedRoles: input.execution.selectedRoles,
        providerStatus: input.execution.providerStatus,
        controlRunId: input.execution.controlRunId,
        validationSummary: input.execution.validationSummary.slice(0, 4000),
      },
    })
    .where(eq(swarms.id, input.swarmId));
}

function selectAgentsForQuery(
  query: string,
  allAgents: Array<{
    id: number;
    name: string;
    slug: string;
    specialty: string | null;
    capabilities: string[] | null;
  }>,
) {
  const q = query.toLowerCase();
  const scores = allAgents.map((agent) => {
    let score = 0;
    const caps = (agent.capabilities ?? []).join(" ").toLowerCase();

    if (/(code|program|debug|function|api|integrat|database)/.test(q)) {
      if (agent.slug === "coder") score += 10;
    }
    if (/(analy|data|statistics|trend|risk|architecture)/.test(q)) {
      if (agent.slug === "analyst") score += 10;
    }
    if (/(research|find|search|information|source|guide)/.test(q)) {
      if (agent.slug === "researcher") score += 10;
    }
    if (/(write|create|design|story|canva|visual)/.test(q)) {
      if (agent.slug === "creative") score += 10;
    }
    if (/(check|verify|validate|fact|safety|compliance)/.test(q)) {
      if (agent.slug === "validator") score += 10;
    }
    if (/(plan|organize|schedule|task|workflow)/.test(q)) {
      if (agent.slug === "planner") score += 10;
    }

    if (agent.slug === "planner") score += 7;
    if (agent.slug === "validator") score += 7;
    if (agent.slug === "synthesizer") score += 6;
    if (agent.slug === "memory") score += 2;

    if (caps.includes("search") && /(find|look up|research)/.test(q)) score += 3;
    if (caps.includes("analysis") && /(analy|compare)/.test(q)) score += 3;

    return { agent, score };
  });

  scores.sort((a, b) => b.score - a.score);
  const positive = scores.filter((entry) => entry.score > 0);
  const count = Math.min(Math.max(4, positive.length), 7);
  return scores.slice(0, count).map((entry) => entry.agent);
}
