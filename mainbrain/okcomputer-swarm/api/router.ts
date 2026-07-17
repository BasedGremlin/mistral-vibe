import { authRouter } from "./auth-router";
import { agentRouter } from "./agent-router";
import { adminRouter } from "./admin-router";
import { createRouter, publicQuery } from "./middleware";

export const appRouter = createRouter({
  ping: publicQuery.query(() => ({ ok: true, ts: Date.now() })),
  auth: authRouter,
  agent: agentRouter,
  admin: adminRouter,
});

export type AppRouter = typeof appRouter;
