import {
  mysqlTable,
  mysqlEnum,
  serial,
  varchar,
  text,
  timestamp,
  bigint,
  json,
  int,
} from "drizzle-orm/mysql-core";

export const users = mysqlTable("users", {
  id: serial("id").primaryKey(),
  unionId: varchar("unionId", { length: 255 }).notNull().unique(),
  name: varchar("name", { length: 255 }),
  email: varchar("email", { length: 320 }),
  avatar: text("avatar"),
  role: mysqlEnum("role", ["user", "admin"]).default("user").notNull(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt")
    .defaultNow()
    .notNull()
    .$onUpdate(() => new Date()),
  lastSignInAt: timestamp("lastSignInAt").defaultNow().notNull(),
});

export type User = typeof users.$inferSelect;
export type InsertUser = typeof users.$inferInsert;

export const agents = mysqlTable("agents", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  slug: varchar("slug", { length: 100 }).notNull().unique(),
  description: text("description"),
  icon: varchar("icon", { length: 100 }).default("bot"),
  color: varchar("color", { length: 20 }).default("#5B21FF"),
  specialty: varchar("specialty", { length: 255 }),
  status: mysqlEnum("status", ["active", "idle", "offline"]).default("idle").notNull(),
  totalTasks: int("totalTasks").default(0),
  successRate: int("successRate").default(95),
  avgLatency: int("avgLatency").default(120),
  capabilities: json("capabilities").$type<string[]>(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().notNull().$onUpdate(() => new Date()),
});

export type Agent = typeof agents.$inferSelect;
export type InsertAgent = typeof agents.$inferInsert;

export const swarms = mysqlTable("swarms", {
  id: serial("id").primaryKey(),
  name: varchar("name", { length: 255 }).notNull(),
  query: text("query").notNull(),
  status: mysqlEnum("status", ["running", "completed", "failed", "paused"]).default("running").notNull(),
  agentCount: int("agentCount").default(0),
  userId: bigint("userId", { mode: "number", unsigned: true }),
  summary: text("summary"),
  metadata: json("metadata").$type<Record<string, unknown>>(),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  updatedAt: timestamp("updatedAt").defaultNow().notNull().$onUpdate(() => new Date()),
  completedAt: timestamp("completedAt"),
});

export type Swarm = typeof swarms.$inferSelect;
export type InsertSwarm = typeof swarms.$inferInsert;

export const swarmAgents = mysqlTable("swarm_agents", {
  id: serial("id").primaryKey(),
  swarmId: bigint("swarmId", { mode: "number", unsigned: true }).notNull(),
  agentId: bigint("agentId", { mode: "number", unsigned: true }).notNull(),
  role: mysqlEnum("role", ["leader", "worker", "validator", "orchestrator"]).default("worker").notNull(),
  status: mysqlEnum("status", ["active", "completed", "failed", "waiting"]).default("waiting").notNull(),
  contribution: text("contribution"),
  startedAt: timestamp("startedAt").defaultNow().notNull(),
  completedAt: timestamp("completedAt"),
});

export type SwarmAgent = typeof swarmAgents.$inferSelect;

export const messages = mysqlTable("messages", {
  id: serial("id").primaryKey(),
  swarmId: bigint("swarmId", { mode: "number", unsigned: true }).notNull(),
  agentId: bigint("agentId", { mode: "number", unsigned: true }),
  role: mysqlEnum("role", ["user", "agent", "system"]).notNull(),
  content: text("content").notNull(),
  sources: json("sources").$type<Array<{ title: string; url: string; snippet: string }>>(),
  reasoning: text("reasoning"),
  tokens: int("tokens").default(0),
  latency: int("latency").default(0),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
});

export type Message = typeof messages.$inferSelect;
export type InsertMessage = typeof messages.$inferInsert;

export const tasks = mysqlTable("tasks", {
  id: serial("id").primaryKey(),
  swarmId: bigint("swarmId", { mode: "number", unsigned: true }).notNull(),
  agentId: bigint("agentId", { mode: "number", unsigned: true }),
  title: varchar("title", { length: 255 }).notNull(),
  description: text("description"),
  status: mysqlEnum("status", ["pending", "running", "completed", "failed"]).default("pending").notNull(),
  priority: mysqlEnum("priority", ["low", "medium", "high", "critical"]).default("medium").notNull(),
  result: text("result"),
  createdAt: timestamp("createdAt").defaultNow().notNull(),
  completedAt: timestamp("completedAt"),
});

export type Task = typeof tasks.$inferSelect;
