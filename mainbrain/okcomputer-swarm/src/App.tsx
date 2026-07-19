import { Routes, Route } from "react-router";
import Layout from "@/components/Layout";
import Home from "./pages/Home";
import Login from "./pages/Login";
import SwarmWorkspace from "./pages/SwarmWorkspace";
import AgentGallery from "./pages/AgentGallery";
import History from "./pages/History";
import AdminDashboard from "./pages/AdminDashboard";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/swarm/:swarmId" element={<SwarmWorkspace />} />
        <Route path="/agents" element={<AgentGallery />} />
        <Route path="/history" element={<History />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}
