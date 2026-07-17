import { Link } from "react-router";
import { Hexagon, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-[calc(100dvh-64px-60px)] flex items-center justify-center px-4">
      <div className="text-center space-y-6">
        <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
          <div className="absolute inset-0 bg-[#5B21FF]/10 rounded-full blur-2xl" />
          <Hexagon className="w-16 h-16 text-[#27272a]" strokeWidth={1} />
          <span className="absolute text-2xl font-bold text-[#52525B]">404</span>
        </div>

        <div>
          <h1 className="text-xl font-bold text-[#FAFAFA] mb-2">
            Swarm Node Not Found
          </h1>
          <p className="text-sm text-[#A1A1AA]">
            The agent you're looking for doesn't exist in this swarm.
          </p>
        </div>

        <Link
          to="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#5B21FF] text-white text-sm font-medium hover:bg-[#5B21FF]/80 transition-all"
        >
          <ArrowLeft className="w-4 h-4" />
          Return to Base
        </Link>
      </div>
    </div>
  );
}
