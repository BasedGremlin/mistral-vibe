import { Button } from "@/components/ui/button";
import { Hexagon, Sparkles, ArrowRight } from "lucide-react";

function getOAuthUrl() {
  const kimiAuthUrl = import.meta.env.VITE_KIMI_AUTH_URL;
  const appID = import.meta.env.VITE_APP_ID;
  const redirectUri = `${window.location.origin}/api/oauth/callback`;
  const state = btoa(redirectUri);

  const url = new URL(`${kimiAuthUrl}/api/oauth/authorize`);
  url.searchParams.set("client_id", appID);
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", "profile");
  url.searchParams.set("state", state);

  return url.toString();
}

export default function Login() {
  return (
    <div className="min-h-[calc(100dvh-64px-60px)] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        {/* Card */}
        <div className="p-8 rounded-2xl bg-[#0a0a0a]/80 border border-[#27272a]/40 backdrop-blur-sm">
          {/* Logo */}
          <div className="flex justify-center mb-6">
            <div className="relative w-16 h-16 flex items-center justify-center">
              <div className="absolute inset-0 bg-[#5B21FF]/20 rounded-full blur-xl" />
              <Hexagon className="w-10 h-10 text-[#5B21FF]" strokeWidth={1.5} />
            </div>
          </div>

          {/* Title */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-[#FAFAFA] mb-2">
              Welcome to Swarm<span className="text-[#FFD600]">OS</span>
            </h1>
            <p className="text-sm text-[#A1A1AA]">
              Sign in to deploy your agent swarm
            </p>
          </div>

          {/* Features */}
          <div className="space-y-3 mb-8">
            {[
              { icon: Sparkles, text: "Multi-agent swarm intelligence" },
              { icon: Hexagon, text: "8 specialized AI agents" },
              { icon: ArrowRight, text: "Real-time collaboration" },
            ].map((item, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-4 py-2.5 rounded-lg bg-white/[0.03] border border-white/5"
              >
                <item.icon className="w-4 h-4 text-[#5B21FF]" />
                <span className="text-sm text-[#A1A1AA]">{item.text}</span>
              </div>
            ))}
          </div>

          {/* Sign In Button */}
          <Button
            className="w-full bg-[#5B21FF] hover:bg-[#5B21FF]/80 text-white font-medium py-6 rounded-xl transition-all duration-300 glow-nova"
            size="lg"
            onClick={() => {
              window.location.href = getOAuthUrl();
            }}
          >
            <Hexagon className="w-4 h-4 mr-2" />
            Sign in with Kimi
          </Button>

          <p className="text-center text-xs text-[#52525B] mt-4">
            Secure OAuth 2.0 authentication
          </p>
        </div>
      </div>
    </div>
  );
}
