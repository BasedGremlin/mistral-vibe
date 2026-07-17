import { z } from "zod";
import { createRouter, adminQuery } from "./middleware";
import { getDb } from "./queries/connection";
import { users, agents, swarms, messages, tasks } from "@db/schema";
import { eq, desc, sql, count } from "drizzle-orm";

export const adminRouter = createRouter({
  dashboard: adminQuery.query(async () => {
    const db = getDb();

    const [userStats] = await db
      .select({
        totalUsers: count(),
        adminUsers: sql<number>`sum(case when ${users.role} = 'admin' then 1 else 0 end)`,
        newUsersToday: sql<number>`sum(case when date(${users.createdAt}) = curdate() then 1 else 0 end)`,
      })
      .from(users);

    const [swarmStats] = await db
      .select({
        totalSwarms: count(),
        runningSwarms: sql<number>`sum(case when ${swarms.status} = 'running' then 1 else 0 end)`,
        completedSwarms: sql<number>`sum(case when ${swarms.status} = 'completed' then 1 else 0 end)`,
      })
      .from(swarms);

    const [messageStats] = await db
      .select({
        totalMessages: count(),
        userMessages: sql<number>`sum(case when ${messages.role} = 'user' then 1 else 0 end)`,
        agentMessages: sql<number>`sum(case when ${messages.role} = 'agent' then 1 else 0 end)`,
      })
      .from(messages);

    const [taskStats] = await db
      .select({
        totalTasks: count(),
        completedTasks: sql<number>`sum(case when ${tasks.status} = 'completed' then 1 else 0 end)`,
        failedTasks: sql<number>`sum(case when ${tasks.status} = 'failed' then 1 else 0 end)`,
      })
      .from(tasks);

    const agentList = await db
      .select({
        id: agents.id,
        name: agents.name,
        slug: agents.slug,
        status: agents.status,
        totalTasks: agents.totalTasks,
        successRate: agents.successRate,
        avgLatency: agents.avgLatency,
        specialty: agents.specialty,
      })
      .from(agents)
      .orderBy(desc(agents.totalTasks));

    return {
      users: userStats,
      swarms: swarmStats,
      messages: messageStats,
      tasks: taskStats,
      agents: agentList,
    };
  }),

  users: adminQuery
    .input(
      z
        .object({
          page: z.number().default(1),
          limit: z.number().default(20),
        })
        .optional()
    )
    .query(async ({ input }) => {
      const db = getDb();
      const page = input?.page ?? 1;
      const limit = input?.limit ?? 20;
      const offset = (page - 1) * limit;

      const userList = await db
        .select()
        .from(users)
        .orderBy(desc(users.createdAt))
        .limit(limit)
        .offset(offset);

      const [total] = await db.select({ count: count() }).from(users);

      return { users: userList, total: total.count };
    }),

  swarms: adminQuery.query(async () => {
    const db = getDb();
    return db
      .select()
      .from(swarms)
      .orderBy(desc(swarms.createdAt))
      .limit(100);
  }),

  updateUserRole: adminQuery
    .input(
      z.object({
        userId: z.number(),
        role: z.enum(["user", "admin"]),
      })
    )
    .mutation(async ({ input }) => {
      const db = getDb();
      await db
        .update(users)
        .set({ role: input.role })
        .where(eq(users.id, input.userId));
      return { ok: true };
    }),
});
