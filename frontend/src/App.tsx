import { Routes, Route, Navigate } from "react-router-dom";
import { Layout } from "./components/Layout";
import ChatPage from "./pages/ChatPage";
import EvaluationPage from "./pages/EvaluationPage";
import AgentsPage from "./pages/AgentsPage";
import McpPage from "./pages/McpPage";
import A2APage from "./pages/A2APage";
import ObservabilityPage from "./pages/ObservabilityPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<ChatPage />} />
        <Route path="evaluation" element={<EvaluationPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="mcp" element={<McpPage />} />
        <Route path="a2a" element={<A2APage />} />
        <Route path="observability" element={<ObservabilityPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
