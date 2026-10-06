import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, Health, IngestResult, QueryResult, DocumentAgentResult, JudgeResult } from "../api/client";
import { load, save } from "../lib/storage";

export interface ActiveDoc {
  pdf_hash: string;
  filename: string;
  n_chunks: number;
  from_cache: boolean;
  duration_ms: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content?: string;
  mode?: "rag" | "agent";
  rag?: QueryResult;
  agent?: DocumentAgentResult;
  question?: string;
  judge?: JudgeResult | null;
  ratingSaved?: boolean;
  error?: string;
}

interface Ctx {
  apiKey: string;
  setApiKey: (k: string) => void;
  doc: ActiveDoc | null;
  setDoc: (d: IngestResult | null) => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
  health: Health | null;
  healthError: boolean;
  refreshHealth: () => void;
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
}

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState<string>(() => load("rag.apiKey", ""));
  const [doc, setDocState] = useState<ActiveDoc | null>(() => load<ActiveDoc | null>("rag.doc", null));
  const [theme, setTheme] = useState<"dark" | "light">(() => load("rag.theme", "dark"));
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    save("rag.theme", theme);
  }, [theme]);

  const refreshHealth = useCallback(() => {
    api.health().then((h) => { setHealth(h); setHealthError(false); }).catch(() => { setHealth(null); setHealthError(true); });
  }, []);
  useEffect(() => {
    refreshHealth();
    const t = setInterval(refreshHealth, 20000);
    return () => clearInterval(t);
  }, [refreshHealth]);

  const value = useMemo<Ctx>(() => ({
    apiKey,
    setApiKey: (k) => { setApiKeyState(k); save("rag.apiKey", k); },
    doc,
    setDoc: (d) => {
      setDocState(d);
      save("rag.doc", d);
      setMessages([]);
    },
    theme,
    toggleTheme: () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    health, healthError, refreshHealth,
    messages, setMessages,
  }), [apiKey, doc, theme, health, healthError, refreshHealth, messages]);

  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const c = useContext(AppCtx);
  if (!c) throw new Error("useApp outside AppProvider");
  return c;
}
