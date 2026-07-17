import {
  Globe,
  Database,
  Cpu,
  Server,
  Cloud,
  Zap,
  Shield,
  Code,
  Search,
  Brain,
  Layers,
  Radio,
  Wifi,
  CircuitBoard,
  Network,
} from "lucide-react";

const DATA_NODES = [
  { label: "Indexing web sources...", icon: Globe },
  { label: "Querying knowledge graph", icon: Database },
  { label: "Neural inference active", icon: Brain },
  { label: "Vector search: 12.4M docs", icon: Search },
  { label: "GPU cluster: 8x A100", icon: Cpu },
  { label: "API latency: 23ms", icon: Zap },
  { label: "Semantic parsing", icon: Code },
  { label: "Context retrieval", icon: Layers },
  { label: "Source verification", icon: Shield },
  { label: "Edge nodes: 47 active", icon: Server },
  { label: "Cloud sync: real-time", icon: Cloud },
  { label: "Signal processing", icon: Radio },
  { label: "Mesh network: online", icon: Network },
  { label: "Bandwidth: 10Gbps", icon: Wifi },
  { label: "Circuit analysis", icon: CircuitBoard },
];

export default function NexusRibbon() {
  // Double the nodes for seamless loop
  const allNodes = [...DATA_NODES, ...DATA_NODES];

  return (
    <div className="nexus-ribbon-container py-2">
      <div className="nexus-ribbon-content">
        {allNodes.map((node, i) => {
          const Icon = node.icon;
          return (
            <div key={i} className="nexus-node">
              <Icon className="w-3 h-3 text-[#5B21FF]" />
              <span>{node.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
