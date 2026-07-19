import { useState, useRef } from "react";
import { useNavigate } from "react-router";
import { trpc } from "@/providers/trpc";
import { useAuth } from "@/hooks/useAuth";
import IntelligenceOrbit from "@/components/IntelligenceOrbit";
import NexusRibbon from "@/components/NexusRibbon";
import {
  Send,
  Sparkles,
  Hexagon,
  Database,
  Shield,
  Route,
  ArrowRight,
  Loader2,
} from "lucide-react";

const SUGGESTED_QUERIES = [
  "Audit MASTERZIP v11 and list the exact blockers before VAL-1",
  "Design the Supabase-backed state machine for this swarm",
  "Integrate the OpenAI Agents SDK without rewriting the existing UI",
  "Route this query locally with Hugging Face embeddings",
  "Adversarially verify the P1, P2, and P6 build claims",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [isActive, setIsActive] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const navigate = useNavigate();
  const { user } = useAuth();

  const orchestrate = trpc.agent.orchestrate.useMutation({
    onSuccess: (data) => {
      navigate(`/swarm/${data.swarmId}`);
    },
  });

  const handleSubmit = () => {
    if (!query.trim() || orchestrate.isPending) return;
    if (!user) {
      navigate("/login");
      return;
    }
    orchestrate.mutate({ query: query.trim() });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="min-h-[calc(100dvh-64px-60px)] flex flex-col">
      {/* Hero Section */}
      <div className="flex-1 flex flex-col items-center justify-center px-4 sm:px-6 relative">
        {/* Intelligence Orbit */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <IntelligenceOrbit className="w-full max-w-[600px] opacity-60" />
        </div>

        {/* Content */}
        <div className="relative z-10 w-full max-w-3xl mx-auto text-center space-y-8">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[#5B21FF]/10 border border-[#5B21FF]/20 text-[#5B21FF] text-xs font-mono uppercase tracking-widest fade-up">
            <Sparkles className="w-3.5 h-3.5" />
            Evidence-Driven Agent Orchestration
          </div>

          {/* Headline */}
          <div className="space-y-3 fade-up" style={{ animationDelay: "0.1s" }}>
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight leading-[1.1]">
              <span className="text-[#FAFAFA]">One verified request.</span>
              <br />
              <span className="text-glow-surge">
                <span className="text-[#FFD600]">A real execution swarm.</span>
              </span>
            </h1>
            <p className="text-base sm:text-lg text-[#A1A1AA] max-w-xl mx-auto leading-relaxed">
              OpenAI Agents execute the workflow, Supabase records state,
              Hugging Face routes locally, and an optional Claude critic attacks
              weak outputs before synthesis.
            </p>
          </div>

          {/* Query Input */}
          <div
            className="fade-up"
            style={{ animationDelay: "0.2s" }}
          >
            <div
              className={`relative rounded-2xl border transition-all duration-500 ${
                isActive
                  ? "border-[#5B21FF]/60 bg-[#0a0a0a]/90 glow-nova"
                  : "border-[#27272a]/60 bg-[#0a0a0a]/70"
              }`}
            >
              <textarea
                ref={inputRef}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onFocus={() => setIsActive(true)}
                onBlur={() => setIsActive(false)}
                onKeyDown={handleKeyDown}
                placeholder="Describe the result you want the verified swarm to produce…"
                rows={1}
                className="w-full bg-transparent text-[#FAFAFA] placeholder-[#52525B] px-5 py-4 pr-14 resize-none outline-none text-base leading-relaxed"
                style={{ minHeight: "56px", maxHeight: "200px" }}
              />
              <button
                onClick={handleSubmit}
                disabled={!query.trim() || orchestrate.isPending}
                className={`absolute right-3 top-1/2 -translate-y-1/2 p-2.5 rounded-xl transition-all duration-300 ${
                  query.trim()
                    ? "bg-[#5B21FF] text-white hover:bg-[#5B21FF]/80 glow-nova"
                    : "bg-[#27272a] text-[#52525B]"
                }`}
              >
                {orchestrate.isPending ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>

            {/* Suggested Queries */}
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {SUGGESTED_QUERIES.map((q, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setQuery(q);
                    inputRef.current?.focus();
                  }}
                  className="px-3 py-1.5 rounded-full text-xs font-medium bg-white/5 border border-white/10 text-[#A1A1AA] hover:text-[#FAFAFA] hover:border-[#5B21FF]/40 hover:bg-[#5B21FF]/10 transition-all duration-300"
                >
                  {q}
                </button>
              ))}
            </div>
            {orchestrate.isPending && (
              <p className="mt-3 text-xs font-mono text-[#00E5FF]">
                Running real provider calls and persisting validation checkpoints…
              </p>
            )}
            {orchestrate.error && (
              <p className="mt-3 text-xs text-red-400">
                {orchestrate.error.message}
              </p>
            )}
          </div>

          {/* Feature Pills */}
          <div
            className="flex flex-wrap justify-center gap-4 pt-4 fade-up"
            style={{ animationDelay: "0.3s" }}
          >
            {[
              { icon: Hexagon, label: "OpenAI Agents SDK" },
              { icon: Database, label: "Supabase Checkpoints" },
              { icon: Route, label: "Local HF Routing" },
              { icon: Shield, label: "Adversarial Validation" },
            ].map((feature, i) => (
              <div
                key={i}
                className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/5"
              >
                <feature.icon className="w-3.5 h-3.5 text-[#5B21FF]" />
                <span className="text-xs font-medium text-[#A1A1AA]">
                  {feature.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Nexus Ribbon */}
      <div className="relative z-10 border-t border-[#27272a]/30">
        <NexusRibbon />
      </div>

      {/* How It Works Section */}
      <section className="relative z-10 py-20 px-4 sm:px-6 border-t border-[#27272a]/30">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <h2 className="text-2xl sm:text-3xl font-bold text-[#FAFAFA] mb-3">
              How the Swarm Works
            </h2>
            <p className="text-[#A1A1AA] max-w-lg mx-auto">
              Every run follows explicit states, provider routes, and evidence gates
            </p>
          </div>

          <div className="grid sm:grid-cols-3 gap-6">
            {[
              {
                step: "01",
                title: "Decompose",
                desc: "The planner reads the canonical project state, identifies blocked inputs, and creates a dependency-aware plan with approval gates.",
                color: "#5B21FF",
              },
              {
                step: "02",
                title: "Collaborate",
                desc: "Hugging Face local embeddings or deterministic fallback select bounded specialist workstreams. OpenAI agents execute them in parallel.",
                color: "#00E5FF",
              },
              {
                step: "03",
                title: "Synthesize",
                desc: "An optional Claude critic attacks the draft, the validator rejects unsupported claims, and Supabase stores only control-plane checkpoints.",
                color: "#FFD600",
              },
            ].map((item, i) => (
              <div
                key={i}
                className="group relative p-6 rounded-2xl bg-[#0a0a0a]/60 border border-[#27272a]/40 hover:border-[#27272a]/80 transition-all duration-500"
              >
                <div
                  className="absolute top-0 left-6 -translate-y-1/2 px-3 py-1 rounded-full text-xs font-mono font-bold"
                  style={{
                    backgroundColor: `${item.color}15`,
                    color: item.color,
                    border: `1px solid ${item.color}30`,
                  }}
                >
                  {item.step}
                </div>
                <h3 className="text-lg font-semibold text-[#FAFAFA] mt-3 mb-2">
                  {item.title}
                </h3>
                <p className="text-sm text-[#A1A1AA] leading-relaxed">
                  {item.desc}
                </p>
                <div
                  className="mt-4 h-0.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-500"
                  style={{
                    background: `linear-gradient(to right, ${item.color}, transparent)`,
                  }}
                />
              </div>
            ))}
          </div>

          {/* CTA */}
          <div className="mt-14 text-center">
            <button
              onClick={() => {
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-[#5B21FF] text-white font-medium hover:bg-[#5B21FF]/80 transition-all duration-300 glow-nova"
            >
              Launch Swarm
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
