import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router";
import { trpc } from "@/providers/trpc";
import { useAuth } from "@/hooks/useAuth";
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  Clock3,
  Database,
  Hexagon,
  Loader2,
  RotateCcw,
  Route,
  Send,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";

type TraceMetadata = {
  provider?: string;
  phase?: string;
  trace?: string;
};

function parseTrace(value: string | null): TraceMetadata {
  if (!value) return {};
  try {
    return JSON.parse(value) as TraceMetadata;
  } catch {
    return {};
  }
}

export default function SwarmWorkspace() {
  const { swarmId } = useParams<{ swarmId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth({ redirectOnUnauthenticated: true });
  const [followUp, setFollowUp] = useState("");

  const numericSwarmId = Number(swarmId);
  const {
    data: swarm,
    isLoading,
    refetch,
  } = trpc.agent.getSwarm.useQuery(
    { id: numericSwarmId },
    {
      enabled: Boolean(swarmId) && !Number.isNaN(numericSwarmId),
      refetchInterval: (query) =>
        query.state.data?.status === "running" ? 2000 : false,
    },
  );

  const addMessage = trpc.agent.addMessage.useMutation({
    onSuccess: async () => {
      setFollowUp("");
      await refetch();
    },
  });

  const metadata = (swarm?.metadata ?? {}) as Record<string, unknown>;
  const providerStatus = (metadata.providerStatus ?? {}) as Record<
    string,
    { configured?: boolean; enabled?: boolean; model?: string }
  >;

  const agentMap = useMemo(() => {
    const map = new Map<number, NonNullable<typeof swarm>["agents"][number]["agent"]>();
    for (const item of swarm?.agents ?? []) {
      if (item.agent) map.set(item.agentId, item.agent);
    }
    return map;
  }, [swarm]);

  const executionMessages = (swarm?.messages ?? []).filter(
    (message) => message.role !== "user",
  );

  const handleFollowUp = () => {
    const content = followUp.trim();
    if (!content || !swarm || addMessage.isPending) return;
    addMessage.mutate({
      swarmId: swarm.id,
      role: "user",
      content,
    });
  };

  if (isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="flex items-center gap-3 text-[#A1A1AA]">
          <Loader2 className="h-5 w-5 animate-spin text-[#5B21FF]" />
          <span className="font-mono text-sm">Loading persisted swarm run…</span>
        </div>
      </div>
    );
  }

  if (!swarm) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <AlertCircle className="h-10 w-10 text-[#52525B]" />
        <p className="text-[#A1A1AA]">Swarm session not found.</p>
        <button
          onClick={() => navigate("/")}
          className="rounded-lg bg-[#5B21FF] px-4 py-2 text-sm font-medium text-white"
        >
          Start a new run
        </button>
      </div>
    );
  }

  const isRunning = swarm.status === "running";
  const isFailed = swarm.status === "failed";
  const completedAgents = swarm.agents.filter(
    (item) => item.status === "completed",
  ).length;

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-64px)] w-full max-w-[1500px] flex-col lg:flex-row">
      <aside className="border-b border-[#27272a]/50 p-4 lg:w-80 lg:border-b-0 lg:border-r">
        <div className="space-y-4 lg:sticky lg:top-20">
          <section className="rounded-2xl border border-[#27272a]/60 bg-[#080808]/80 p-4">
            <div className="mb-3 flex items-center gap-2">
              <Hexagon className="h-4 w-4 text-[#5B21FF]" />
              <span className="font-mono text-xs font-bold uppercase tracking-wider text-[#A1A1AA]">
                Swarm #{swarm.id}
              </span>
            </div>
            <p className="mb-4 line-clamp-4 text-sm leading-relaxed text-[#FAFAFA]">
              {swarm.query}
            </p>
            <div className="flex items-center justify-between text-xs">
              <span
                className={
                  isFailed
                    ? "text-red-400"
                    : isRunning
                      ? "text-[#00E5FF]"
                      : "text-[#10B981]"
                }
              >
                {isFailed
                  ? "Failed safely"
                  : isRunning
                    ? "Executing"
                    : "Completed"}
              </span>
              <span className="text-[#71717A]">
                {completedAgents}/{swarm.agents.length} persisted
              </span>
            </div>
          </section>

          <section className="rounded-2xl border border-[#27272a]/60 bg-[#080808]/70 p-4">
            <div className="mb-3 flex items-center gap-2">
              <Route className="h-4 w-4 text-[#FACC15]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#A1A1AA]">
                Provider routes
              </h2>
            </div>
            <div className="space-y-2 text-xs">
              <ProviderRow
                label="OpenAI Agents"
                model={providerStatus.openai?.model}
                ready={providerStatus.openai?.configured}
              />
              <ProviderRow
                label="Claude critic"
                model={providerStatus.anthropic?.model}
                ready={providerStatus.anthropic?.configured}
                optional
              />
              <ProviderRow
                label="HF local router"
                model={providerStatus.huggingface?.model}
                ready={providerStatus.huggingface?.enabled}
              />
              <ProviderRow
                label="Supabase control"
                ready={providerStatus.supabase?.configured}
              />
            </div>
          </section>

          <section className="rounded-2xl border border-[#27272a]/60 bg-[#080808]/70 p-4">
            <div className="mb-3 flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-[#10B981]" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#A1A1AA]">
                Execution trace
              </h2>
            </div>
            <div className="space-y-2">
              {[
                ["PLAN", "Dependency plan"],
                ["ROUTE", "Provider and role routing"],
                ["EXECUTE", "Specialist workstreams"],
                ["CRITIQUE", "Optional cross-provider attack"],
                ["VALIDATE", "Adversarial verification"],
                ["PERSIST", "Checkpoint and synthesis"],
              ].map(([phase, label]) => {
                const reached = executionMessages.some(
                  (message) => parseTrace(message.reasoning).phase === phase,
                );
                return (
                  <div
                    key={phase}
                    className="flex items-center gap-2 rounded-lg bg-white/[0.025] px-3 py-2"
                  >
                    {reached ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-[#10B981]" />
                    ) : isRunning ? (
                      <Clock3 className="h-3.5 w-3.5 text-[#52525B]" />
                    ) : (
                      <AlertCircle className="h-3.5 w-3.5 text-[#52525B]" />
                    )}
                    <span className="font-mono text-[10px] text-[#71717A]">
                      {phase}
                    </span>
                    <span className="text-xs text-[#A1A1AA]">{label}</span>
                  </div>
                );
              })}
            </div>
          </section>

          <button
            onClick={() => navigate("/")}
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs text-[#A1A1AA] transition hover:bg-white/10 hover:text-white"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            New swarm
          </button>
        </div>
      </aside>

      <main className="flex min-h-0 flex-1 flex-col">
        <header className="border-b border-[#27272a]/40 px-5 py-4 sm:px-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold text-white">
                Evidence-driven swarm run
              </h1>
              <p className="mt-1 text-xs text-[#71717A]">
                Stored outputs are decision summaries, not private chain-of-thought.
              </p>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-[#27272a] bg-[#0A0A0A] px-3 py-1.5 text-xs text-[#A1A1AA]">
              <Database className="h-3.5 w-3.5 text-[#8B5CF6]" />
              Control run:{" "}
              {typeof metadata.controlRunId === "string"
                ? metadata.controlRunId.slice(0, 8)
                : "local only"}
            </div>
          </div>
        </header>

        <div className="flex-1 space-y-6 overflow-y-auto p-5 sm:p-7">
          <MessageCard
            role="user"
            name={user?.name || "You"}
            content={swarm.query}
          />

          {executionMessages.length === 0 && isRunning && (
            <div className="flex items-center gap-3 rounded-2xl border border-[#00E5FF]/20 bg-[#00E5FF]/5 p-4 text-sm text-[#A1A1AA]">
              <Loader2 className="h-4 w-4 animate-spin text-[#00E5FF]" />
              Real providers are executing. No simulated messages are shown.
            </div>
          )}

          {executionMessages.map((message) => {
            const agent = message.agentId
              ? agentMap.get(message.agentId)
              : undefined;
            const trace = parseTrace(message.reasoning);
            return (
              <MessageCard
                key={message.id}
                role={message.role}
                name={
                  message.role === "system"
                    ? "System"
                    : agent?.name ?? "Swarm agent"
                }
                color={agent?.color ?? "#5B21FF"}
                content={message.content}
                provider={trace.provider}
                phase={trace.phase}
                latency={message.latency}
              />
            );
          })}

          {swarm.summary && !isRunning && (
            <section className="rounded-2xl border border-[#5B21FF]/30 bg-[#5B21FF]/[0.06] p-5">
              <div className="mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-[#A78BFA]" />
                <h2 className="text-sm font-semibold text-white">
                  Persisted final synthesis
                </h2>
              </div>
              <div className="whitespace-pre-wrap text-sm leading-7 text-[#D4D4D8]">
                {swarm.summary}
              </div>
            </section>
          )}
        </div>

        <footer className="border-t border-[#27272a]/40 p-4 sm:p-5">
          <div className="mx-auto flex max-w-4xl gap-3">
            <textarea
              value={followUp}
              onChange={(event) => setFollowUp(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  handleFollowUp();
                }
              }}
              placeholder="Run a verified follow-up through the same provider stack…"
              rows={2}
              className="min-h-[52px] flex-1 resize-none rounded-xl border border-[#27272a] bg-[#080808] px-4 py-3 text-sm text-white outline-none transition placeholder:text-[#52525B] focus:border-[#5B21FF]/60"
            />
            <button
              onClick={handleFollowUp}
              disabled={!followUp.trim() || addMessage.isPending}
              className="flex h-[52px] w-[52px] items-center justify-center rounded-xl bg-[#5B21FF] text-white transition hover:bg-[#6D37FF] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {addMessage.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
          {addMessage.error && (
            <p className="mx-auto mt-2 max-w-4xl text-xs text-red-400">
              {addMessage.error.message}
            </p>
          )}
        </footer>
      </main>
    </div>
  );
}

function ProviderRow({
  label,
  model,
  ready,
  optional = false,
}: {
  label: string;
  model?: string;
  ready?: boolean;
  optional?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.025] px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-[#D4D4D8]">{label}</p>
        {model && <p className="truncate text-[10px] text-[#52525B]">{model}</p>}
      </div>
      <span
        className={
          ready
            ? "text-[#10B981]"
            : optional
              ? "text-[#F59E0B]"
              : "text-[#71717A]"
        }
      >
        {ready ? "ready" : optional ? "optional" : "setup"}
      </span>
    </div>
  );
}

function MessageCard({
  role,
  name,
  color = "#5B21FF",
  content,
  provider,
  phase,
  latency,
}: {
  role: string;
  name: string;
  color?: string;
  content: string;
  provider?: string;
  phase?: string;
  latency?: number | null;
}) {
  const isUser = role === "user";
  const isSystem = role === "system";

  return (
    <article className="flex gap-3">
      <div
        className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-xl border"
        style={{
          borderColor: isUser ? "#5B21FF55" : `${color}55`,
          backgroundColor: isUser ? "#5B21FF18" : `${color}18`,
        }}
      >
        {isUser ? (
          <User className="h-4 w-4 text-[#A78BFA]" />
        ) : isSystem ? (
          <AlertCircle className="h-4 w-4 text-[#F59E0B]" />
        ) : (
          <Bot className="h-4 w-4" style={{ color }} />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-white">{name}</span>
          {provider && (
            <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 font-mono text-[10px] text-[#A1A1AA]">
              {provider}
            </span>
          )}
          {phase && (
            <span className="rounded-full border border-[#5B21FF]/20 bg-[#5B21FF]/10 px-2 py-0.5 font-mono text-[10px] text-[#A78BFA]">
              {phase}
            </span>
          )}
          {latency ? (
            <span className="text-[10px] text-[#52525B]">
              {(latency / 1000).toFixed(1)}s
            </span>
          ) : null}
        </div>
        <div className="whitespace-pre-wrap rounded-2xl border border-[#27272a]/50 bg-[#080808]/70 p-4 text-sm leading-7 text-[#D4D4D8]">
          {content}
        </div>
      </div>
    </article>
  );
}
