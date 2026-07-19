import { trpc } from "@/providers/trpc";
import { useNavigate } from "react-router";
import {
  Hexagon,
  Clock,
  CheckCircle2,
  Loader2,
  ArrowRight,
  Bot,
  MessageSquare,
  Calendar,
  Search,
} from "lucide-react";
import { useState } from "react";

export default function History() {
  const navigate = useNavigate();
  const { data: swarms, isLoading } = trpc.agent.history.useQuery();
  const [filter, setFilter] = useState("");

  const filteredSwarms =
    swarms?.filter((s) =>
      s.query.toLowerCase().includes(filter.toLowerCase())
    ) ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex items-center gap-3 text-[#A1A1AA]">
          <Loader2 className="w-5 h-5 animate-spin text-[#5B21FF]" />
          <span className="text-sm font-mono">Loading history...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-[#FAFAFA] mb-1">
            Swarm History
          </h1>
          <p className="text-[#A1A1AA] text-sm">
            {swarms?.length ?? 0} completed swarm sessions
          </p>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#52525B]" />
          <input
            type="text"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search sessions..."
            className="pl-10 pr-4 py-2.5 rounded-xl bg-[#0a0a0a]/60 border border-[#27272a]/40 text-sm text-[#FAFAFA] placeholder-[#52525B] outline-none focus:border-[#5B21FF]/60 transition-all w-full sm:w-64"
          />
        </div>
      </div>

      {/* Swarm List */}
      {filteredSwarms.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Hexagon className="w-12 h-12 text-[#27272a]" />
          <p className="text-[#52525B]">
            {filter ? "No matching sessions found" : "No swarm history yet"}
          </p>
          <button
            onClick={() => navigate("/")}
            className="px-4 py-2 rounded-lg bg-[#5B21FF] text-white text-sm font-medium hover:bg-[#5B21FF]/80 transition-all"
          >
            Start Your First Swarm
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredSwarms.map((swarm) => (
            <button
              key={swarm.id}
              onClick={() => navigate(`/swarm/${swarm.id}`)}
              className="w-full text-left p-5 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40 hover:border-[#5B21FF]/30 hover:bg-[#0a0a0a]/80 transition-all duration-300 group"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  {/* Title & Status */}
                  <div className="flex items-center gap-3 mb-2">
                    <span className="flex items-center gap-1.5 text-xs font-mono">
                      <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />
                      <span className="text-[#10B981]">Completed</span>
                    </span>
                    <span className="text-[#52525B]">|</span>
                    <span className="flex items-center gap-1.5 text-xs text-[#52525B]">
                      <Calendar className="w-3 h-3" />
                      {new Date(swarm.createdAt).toLocaleDateString()}
                    </span>
                    <span className="text-[#52525B]">|</span>
                    <span className="flex items-center gap-1.5 text-xs text-[#52525B]">
                      <Clock className="w-3 h-3" />
                      {new Date(swarm.createdAt).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Query */}
                  <h3 className="text-sm font-semibold text-[#FAFAFA] mb-2 truncate">
                    {swarm.query}
                  </h3>

                  {/* Agents & Messages */}
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5">
                      <Bot className="w-3.5 h-3.5 text-[#5B21FF]" />
                      <span className="text-xs text-[#A1A1AA]">
                        {swarm.agents?.length ?? 0} agents
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <MessageSquare className="w-3.5 h-3.5 text-[#00E5FF]" />
                      <span className="text-xs text-[#A1A1AA]">
                        {swarm.messageCount} messages
                      </span>
                    </div>

                    {/* Agent badges */}
                    <div className="hidden sm:flex items-center gap-1">
                      {swarm.agents?.slice(0, 4).map((agent, j) => (
                        <div
                          key={j}
                          className="w-5 h-5 rounded-full flex items-center justify-center"
                          style={{
                            backgroundColor: `${agent.color ?? "#5B21FF"}20`,
                            border: `1px solid ${agent.color ?? "#5B21FF"}40`,
                          }}
                          title={agent.name}
                        >
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: agent.color ?? "#5B21FF" }}
                          />
                        </div>
                      ))}
                      {(swarm.agents?.length ?? 0) > 4 && (
                        <span className="text-[10px] text-[#52525B] font-mono ml-0.5">
                          +{(swarm.agents?.length ?? 0) - 4}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Arrow */}
                <ArrowRight className="w-5 h-5 text-[#52525B] group-hover:text-[#5B21FF] group-hover:translate-x-1 transition-all duration-300 flex-shrink-0 mt-1" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
