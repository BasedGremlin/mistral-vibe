import { trpc } from "@/providers/trpc";
import { useAuth } from "@/hooks/useAuth";
import { useNavigate } from "react-router";
import { useEffect, useState } from "react";
import {
  Users,
  Hexagon,
  MessageSquare,
  CheckSquare,
  Bot,
  Shield,
  Loader2,
  AlertCircle,
  Activity,
  Zap,
  Clock,
  BarChart3,
} from "lucide-react";

export default function AdminDashboard() {
  const { isAdmin, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!authLoading && !isAdmin) {
      navigate("/");
    }
  }, [authLoading, isAdmin, navigate]);

  const { data: dashboard, isLoading: dashLoading } =
    trpc.admin.dashboard.useQuery(undefined, { enabled: isAdmin });

  const { data: usersData } = trpc.admin.users.useQuery(
    { page, limit: 10 },
    { enabled: isAdmin }
  );

  if (authLoading || dashLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-[#A1A1AA]">
          <Loader2 className="w-5 h-5 animate-spin text-[#5B21FF]" />
          <span className="text-sm font-mono">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <AlertCircle className="w-10 h-10 text-[#52525B]" />
        <p className="text-[#A1A1AA]">Access denied. Admin only.</p>
        <button
          onClick={() => navigate("/")}
          className="px-4 py-2 rounded-lg bg-[#5B21FF] text-white text-sm font-medium hover:bg-[#5B21FF]/80 transition-all"
        >
          Go Home
        </button>
      </div>
    );
  }

  const statCards = [
    {
      label: "Total Users",
      value: dashboard?.users?.totalUsers ?? 0,
      icon: Users,
      color: "#5B21FF",
      detail: `${dashboard?.users?.adminUsers ?? 0} admins`,
    },
    {
      label: "Total Swarms",
      value: dashboard?.swarms?.totalSwarms ?? 0,
      icon: Hexagon,
      color: "#00E5FF",
      detail: `${dashboard?.swarms?.runningSwarms ?? 0} running`,
    },
    {
      label: "Messages",
      value: dashboard?.messages?.totalMessages ?? 0,
      icon: MessageSquare,
      color: "#FFD600",
      detail: `${dashboard?.messages?.agentMessages ?? 0} agent`,
    },
    {
      label: "Tasks",
      value: dashboard?.tasks?.totalTasks ?? 0,
      icon: CheckSquare,
      color: "#10B981",
      detail: `${dashboard?.tasks?.completedTasks ?? 0} completed`,
    },
  ];

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-[#FFD600]/10 border border-[#FFD600]/20 flex items-center justify-center">
          <Shield className="w-5 h-5 text-[#FFD600]" />
        </div>
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#FAFAFA]">
            Admin Dashboard
          </h1>
          <p className="text-sm text-[#A1A1AA]">
            SwarmOS system analytics and management
          </p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((stat, i) => (
          <div
            key={i}
            className="p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40 fade-up"
            style={{ animationDelay: `${i * 0.05}s` }}
          >
            <div className="flex items-center gap-2 mb-3">
              <stat.icon className="w-4 h-4" style={{ color: stat.color }} />
              <span className="text-xs font-mono text-[#52525B] uppercase tracking-wider">
                {stat.label}
              </span>
            </div>
            <p className="text-3xl font-bold text-[#FAFAFA] mb-1">
              {stat.value}
            </p>
            <p className="text-xs text-[#52525B]">{stat.detail}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Agent Performance */}
        <div className="lg:col-span-2 p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Bot className="w-4 h-4 text-[#5B21FF]" />
              <h2 className="text-base font-semibold text-[#FAFAFA]">
                Agent Performance
              </h2>
            </div>
            <span className="text-xs font-mono text-[#52525B]">
              {dashboard?.agents?.length ?? 0} agents
            </span>
          </div>

          <div className="space-y-3">
            {dashboard?.agents?.map((agent) => {
              const agentColor = agent.slug === "researcher" ? "#5B21FF"
                : agent.slug === "analyst" ? "#00E5FF"
                : agent.slug === "coder" ? "#FFD600"
                : agent.slug === "creative" ? "#FF6B9D"
                : agent.slug === "validator" ? "#10B981"
                : agent.slug === "planner" ? "#F97316"
                : agent.slug === "memory" ? "#8B5CF6"
                : agent.slug === "synthesizer" ? "#EC4899"
                : "#5B21FF";

              return (
                <div
                  key={agent.id}
                  className="flex items-center gap-4 p-3 rounded-xl bg-white/[0.02] border border-white/5"
                >
                  {/* Color indicator */}
                  <div
                    className="w-3 h-3 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor: agentColor,
                      boxShadow: `0 0 8px ${agentColor}`,
                    }}
                  />

                  {/* Name */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[#FAFAFA] truncate">
                      {agent.name}
                    </p>
                    <p className="text-xs text-[#52525B]">{agent.specialty}</p>
                  </div>

                  {/* Metrics */}
                  <div className="flex items-center gap-4 text-xs font-mono">
                    <div className="text-right">
                      <div className="flex items-center gap-1 text-[#A1A1AA]">
                        <Zap className="w-3 h-3" />
                        <span>{agent.totalTasks?.toLocaleString() ?? 0}</span>
                      </div>
                      <span className="text-[#52525B]">tasks</span>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1 text-[#10B981]">
                        <Activity className="w-3 h-3" />
                        <span>{agent.successRate ?? 0}%</span>
                      </div>
                      <span className="text-[#52525B]">success</span>
                    </div>
                    <div className="text-right">
                      <div className="flex items-center gap-1 text-[#00E5FF]">
                        <Clock className="w-3 h-3" />
                        <span>{agent.avgLatency ?? 0}ms</span>
                      </div>
                      <span className="text-[#52525B]">latency</span>
                    </div>
                  </div>

                  {/* Status */}
                  <div
                    className="w-2 h-2 rounded-full flex-shrink-0"
                    style={{
                      backgroundColor:
                        agent.status === "active" ? "#10B981" : "#52525B",
                      boxShadow:
                        agent.status === "active"
                          ? "0 0 6px #10B981"
                          : "none",
                    }}
                  />
                </div>
              );
            })}
          </div>
        </div>

        {/* User Management */}
        <div className="p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40">
          <div className="flex items-center justify-between mb-5">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-[#00E5FF]" />
              <h2 className="text-base font-semibold text-[#FAFAFA]">
                Users
              </h2>
            </div>
            <span className="text-xs font-mono text-[#52525B]">
              {usersData?.total ?? 0} total
            </span>
          </div>

          <div className="space-y-2">
            {usersData?.users?.map((u) => (
              <div
                key={u.id}
                className="flex items-center gap-3 p-3 rounded-xl bg-white/[0.02] border border-white/5"
              >
                <div className="w-8 h-8 rounded-full bg-[#5B21FF]/20 border border-[#5B21FF]/30 flex items-center justify-center flex-shrink-0">
                  <span className="text-xs font-bold text-[#5B21FF]">
                    {(u.name ?? "U").charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-[#FAFAFA] truncate">
                    {u.name || "Anonymous"}
                  </p>
                  <p className="text-xs text-[#52525B] truncate">{u.email}</p>
                </div>
                <span
                  className={`text-[10px] px-2 py-0.5 rounded-full font-mono font-bold uppercase ${
                    u.role === "admin"
                      ? "bg-[#FFD600]/10 text-[#FFD600]"
                      : "bg-white/5 text-[#52525B]"
                  }`}
                >
                  {u.role}
                </span>
              </div>
            ))}
          </div>

          {/* Pagination */}
          {usersData && usersData.total > 10 && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-[#27272a]/30">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="text-xs text-[#52525B] hover:text-[#FAFAFA] disabled:opacity-30 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs font-mono text-[#52525B]">
                Page {page} of {Math.ceil((usersData?.total ?? 0) / 10)}
              </span>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page >= Math.ceil((usersData?.total ?? 0) / 10)}
                className="text-xs text-[#52525B] hover:text-[#FAFAFA] disabled:opacity-30 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Activity Overview */}
      <div className="mt-6 p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40">
        <div className="flex items-center gap-2 mb-5">
          <BarChart3 className="w-4 h-4 text-[#FFD600]" />
          <h2 className="text-base font-semibold text-[#FAFAFA]">
            Activity Overview
          </h2>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[
            {
              label: "User Messages",
              value: dashboard?.messages?.userMessages ?? 0,
              icon: MessageSquare,
              color: "#5B21FF",
            },
            {
              label: "Agent Messages",
              value: dashboard?.messages?.agentMessages ?? 0,
              icon: Bot,
              color: "#00E5FF",
            },
            {
              label: "Completed Tasks",
              value: dashboard?.tasks?.completedTasks ?? 0,
              icon: CheckSquare,
              color: "#10B981",
            },
            {
              label: "Failed Tasks",
              value: dashboard?.tasks?.failedTasks ?? 0,
              icon: AlertCircle,
              color: "#EF4444",
            },
          ].map((item, idx) => (
            <div
              key={idx}
              className="p-4 rounded-xl bg-white/[0.02] border border-white/5"
            >
              <div className="flex items-center gap-2 mb-2">
                <item.icon
                  className="w-3.5 h-3.5"
                  style={{ color: item.color }}
                />
                <span className="text-xs text-[#52525B]">{item.label}</span>
              </div>
              <p className="text-xl font-bold text-[#FAFAFA]">{item.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
