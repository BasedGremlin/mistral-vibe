import { getDb } from "../api/queries/connection";
import { agents } from "./schema";

async function seed() {
  const db = getDb();

  const agentData = [
    {
      name: "Researcher",
      slug: "researcher",
      description:
        "Evidence retrieval specialist. Extracts source-backed facts and marks unavailable evidence instead of inventing it.",
      icon: "search",
      color: "#5B21FF",
      specialty: "Evidence Retrieval",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "source_extraction",
        "documentation_review",
        "fact_classification",
      ],
    },
    {
      name: "Analyst",
      slug: "analyst",
      description:
        "Risk, dependency, uncertainty, and quantitative analysis specialist.",
      icon: "bar-chart-3",
      color: "#00E5FF",
      specialty: "Risk Analysis",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "risk_analysis",
        "dependency_mapping",
        "uncertainty_analysis",
      ],
    },
    {
      name: "Coder",
      slug: "coder",
      description:
        "Implementation specialist for TypeScript, APIs, tests, migrations, and compatibility-preserving changes.",
      icon: "code-2",
      color: "#FFD600",
      specialty: "Implementation",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "code_generation",
        "debugging",
        "testing",
        "integration",
      ],
    },
    {
      name: "Creative",
      slug: "creative",
      description:
        "Design and alternative-generation agent constrained by safety and evidence gates.",
      icon: "sparkles",
      color: "#FF6B9D",
      specialty: "Design Alternatives",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: ["design_ideation", "canva_briefing", "alternatives"],
    },
    {
      name: "Validator",
      slug: "validator",
      description:
        "Adversarial verifier for unsupported claims, missing tests, unsafe assumptions, and state bypasses.",
      icon: "shield-check",
      color: "#10B981",
      specialty: "Verification",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "fact_checking",
        "state_validation",
        "safety_review",
        "compliance_review",
      ],
    },
    {
      name: "Planner",
      slug: "planner",
      description:
        "Dependency-aware workflow architect with approval gates and blocked-state handling.",
      icon: "git-branch",
      color: "#F97316",
      specialty: "Orchestration",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "task_decomposition",
        "workflow_design",
        "approval_gates",
      ],
    },
    {
      name: "Memory",
      slug: "memory",
      description:
        "Context compression and checkpoint agent. Stores no secrets or model binaries.",
      icon: "database",
      color: "#8B5CF6",
      specialty: "Context and Checkpoints",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "context_compression",
        "checkpointing",
        "constraint_retention",
      ],
    },
    {
      name: "Synthesizer",
      slug: "synthesizer",
      description:
        "Final answer assembler that preserves validation limits, disagreements, and exact next actions.",
      icon: "layers",
      color: "#EC4899",
      specialty: "Synthesis",
      status: "active" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: [
        "multi_source_integration",
        "conflict_preservation",
        "summary_generation",
      ],
    },
    {
      name: "Claude Critic",
      slug: "claude-critic",
      description:
        "Optional secondary critic reached through Anthropic's OpenAI SDK compatibility endpoint when ANTHROPIC_API_KEY is configured.",
      icon: "scan-search",
      color: "#D97706",
      specialty: "Cross-provider Critique",
      status: "idle" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: ["cross_provider_review", "failure_analysis"],
    },
    {
      name: "HF Local Router",
      slug: "hf-router",
      description:
        "Local semantic router using Transformers.js embeddings with remote model loading disabled by default.",
      icon: "route",
      color: "#FACC15",
      specialty: "Local Semantic Routing",
      status: "idle" as const,
      totalTasks: 0,
      successRate: 0,
      avgLatency: 0,
      capabilities: ["local_embeddings", "semantic_routing", "offline_cache"],
    },
  ];

  for (const agent of agentData) {
    await db.insert(agents).values(agent).onDuplicateKeyUpdate({
      set: { ...agent, updatedAt: new Date() },
    });
  }

  console.log(`Seeded ${agentData.length} evidence-driven agents`);
}

seed().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
