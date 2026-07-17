import { trpc } from "@/providers/trpc";
import {
  Bot,
  Search,
  BarChart3,
  Code2,
  Sparkles,
  ShieldCheck,
  GitBranch,
  Database,
  Layers,
  Zap,
  TrendingUp,
  Clock,
  CheckCircle2,
  Activity,
} from "lucide-react";

const ICON_MAP: Record<string, React.FC<{ className?: string }>> = {
  search: Search,
  "bar-chart-3": BarChart3,
  "code-2": Code2,
  sparkles: Sparkles,
  "shield-check": ShieldCheck,
  "git-branch": GitBranch,
  database: Database,
  layers: Layers,
  bot: Bot,
};

export default function AgentGallery() {
  const { data: agents, isLoading } = trpc.agent.list.useQuery();
  const { data: stats } = trpc.agent.getStats.useQuery();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-[#A1A1AA]">
          <Activity className="w-5 h-5 animate-pulse text-[#5B21FF]" />
          <span className="text-sm font-mono">Loading agents...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-10">
        <h1 className="text-2xl sm:text-3xl font-bold text-[#FAFAFA] mb-2">
          Agent Gallery
        </h1>
        <p className="text-[#A1A1AA]">
          Browse all specialized agents in the SwarmOS ecosystem
        </p>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
          {[
            {
              label: "Total Agents",
              value: stats.totalAgents ?? 0,
              icon: Bot,
              color: "#5B21FF",
            },
            {
              label: "Active Now",
              value: stats.activeAgents ?? 0,
              icon: Activity,
              color: "#00E5FF",
            },
            {
              label: "Tasks Completed",
              value: stats.totalTasks ?? 0,
              icon: CheckCircle2,
              color: "#10B981",
            },
            {
              label: "Avg Success Rate",
              value: `${Math.round(stats.avgSuccessRate ?? 0)}%`,
              icon: TrendingUp,
              color: "#FFD600",
            },
          ].map((stat, i) => (
            <div
              key={i}
              className="p-4 rounded-xl bg-[#0a0a0a]/60 border border-[#27272a]/40"
            >
              <div className="flex items-center gap-2 mb-2">
                <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
                <span className="text-xs font-mono text-[#52525B] uppercase tracking-wider">
                  {stat.label}
                </span>
              </div>
              <p className="text-2xl font-bold text-[#FAFAFA]">{stat.value}</p>
            </div>
          ))}
        </div>
      )}

      {/* Agent Cards */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {agents?.map((agent, i) => {
          const Icon = ICON_MAP[agent.icon ?? "bot"] ?? Bot;
          const capabilities = (agent.capabilities as string[] | null) ?? [];
          const agentColor = agent.color ?? "#5B21FF";

          return (
            <div
              key={agent.id}
              className="relative group p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40 hover:border-[#27272a]/80 transition-all duration-500 fade-up"
              style={{ animationDelay: `${i * 0.05}s` }}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center"
                  style={{
                    backgroundColor: `${agentColor}15`,
                    border: `1px solid ${agentColor}30`,
                  }}
                >
                  <div style={{ color: agentColor }}>
                    <Icon className="w-5 h-5" />
                  </div>
                </div>
                <div
                  className="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold uppercase"
                  style={{
                    backgroundColor:
                      agent.status === "active"
                        ? "#10B98115"
                        : agent.status === "idle"
                        ? "#FFD60015"
                        : "#52525B15",
                    color:
                      agent.status === "active"
                        ? "#10B981"
                        : agent.status === "idle"
                        ? "#FFD600"
                        : "#52525B",
                    border: `1px solid ${
                      agent.status === "active"
                        ? "#10B98130"
                        : agent.status === "idle"
                        ? "#FFD60030"
                        : "#52525B30"
                    }`,
                  }}
                >
                  {agent.status}
                </div>
              </div>

              {/* Name & Description */}
              <h3 className="text-base font-semibold text-[#FAFAFA] mb-1">
                {agent.name}
              </h3>
              <p className="text-xs text-[#A1A1AA] mb-1 font-mono">
                {agent.specialty}
              </p>
              <p className="text-sm text-[#52525B] mb-4 line-clamp-2 leading-relaxed">
                {agent.description}
              </p>

              {/* Capabilities */}
              <div className="flex flex-wrap gap-1.5 mb-4">
                {capabilities.slice(0, 4).map((cap, j) => (
                  <span
                    key={j}
                    className="px-2 py-0.5 rounded-md bg-white/5 text-[10px] font-mono text-[#A1A1AA] border border-white/5"
                  >
                    {cap}
                  </span>
                ))}
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-3 gap-2 pt-3 border-t border-[#27272a]/30">
                <div>
                  <div className="flex items-center gap-1 mb-0.5">
                    <Zap className="w-3 h-3 text-[#FFD600]" />
                    <span className="text-[10px] text-[#52525B]">Tasks</span>
                  </div>
                  <p className="text-sm font-bold text-[#FAFAFA]">
                    {agent.totalTasks?.toLocaleString() ?? 0}
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-1 mb-0.5">
                    <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
                    <span className="text-[10px] text-[#52525B]">Success</span>
                  </div>
                  <p className="text-sm font-bold text-[#FAFAFA]">
                    {agent.successRate ?? 0}%
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-1 mb-0.5">
                    <Clock className="w-3 h-3 text-[#00E5FF]" />
                    <span className="text-[10px] text-[#52525B]">Latency</span>
                  </div>
                  <p className="text-sm font-bold text-[#FAFAFA]">
                    {agent.avgLatency ?? 0}ms
                  </p>
                </div>
              </div>

              {/* Hover gradient */}
              <div
                className="absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-500 pointer-events-none"
                style={{
                  background: `radial-gradient(circle at 50% 0%, ${agentColor}08, transparent 70%)`,
                }}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
