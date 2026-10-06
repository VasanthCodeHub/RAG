import { useEffect, useRef, useState } from "react";
import { MessageSquare, Send, Bot, Sparkles, Upload, Search, ScanEye, Trash2, Layers, Zap, FileUp } from "lucide-react";
import { api } from "../api/client";
import { useApp, ChatMessage } from "../context/AppContext";
import { PageHero, Card, Stat, Button, Toggle, Badge, useToast, Collapse } from "../components";
import { DocumentUploader } from "../components/chat/DocumentUploader";
import { RagAnswer } from "../components/chat/RagAnswer";
import { AgentAnswer } from "../components/chat/AgentAnswer";
import { PendingAnswer } from "../components/chat/PendingAnswer";
import { JudgePanel } from "../components/chat/JudgePanel";
import { ms } from "../lib/format";

const HOW = [
  { icon: Upload, title: "1. Upload", text: "Drop in any document - PDF, DOCX, TXT, MD, HTML or CSV. It is chunked and embedded automatically; re-uploads are instant.", g: "var(--grad-cool)" },
  { icon: MessageSquare, title: "2. Ask", text: "Chat naturally. Every answer is grounded in retrieved passages, or switch on the tool-calling agent.", g: "var(--grad)" },
  { icon: ScanEye, title: "3. Inspect", text: "See retrieval, rerank scores, timings, cost, cache hits - and have an LLM judge grade each answer.", g: "var(--grad-warm)" },
];

const SUGGESTIONS = ["Summarize this document in 3 bullet points", "What are the key dates or numbers mentioned?", "Who or what is this document about?"];

export default function ChatPage() {
  const { doc, messages, setMessages } = useApp();
  const { toast } = useToast();
  const [input, setInput] = useState("");
  const [agentMode, setAgentMode] = useState(false);
  const [useCache, setUseCache] = useState(true);
  const [pending, setPending] = useState<{ mode: "rag" | "agent" } | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, pending]);

  const patch = (id: string, p: Partial<ChatMessage>) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...p } : m)));

  const send = async (text?: string) => {
    const q = (text ?? input).trim();
    if (!q || !doc || pending) return;
    setInput("");
    const mode = agentMode ? "agent" : "rag";
    const uid = crypto.randomUUID();
    setMessages((m) => [...m, { id: uid, role: "user", content: q }]);
    setPending({ mode });
    try {
      if (mode === "agent") {
        const agent = await api.documentAgent(doc.pdf_hash, q);
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", mode, agent, question: q }]);
      } else {
        const rag = await api.query(doc.pdf_hash, q, useCache);
        setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", mode, rag, question: q }]);
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((m) => [...m, { id: crypto.randomUUID(), role: "assistant", mode, error: msg, question: q }]);
      toast("error", "Question failed", msg);
    } finally {
      setPending(null);
    }
  };

  /* ------------------------------ empty state ------------------------------ */
  if (!doc) {
    return (
      <>
        <PageHero icon={<Layers size={28} />} title="Ask your documents anything">
          Upload any document and inspect exactly how every answer was retrieved, reranked, generated and judged.
        </PageHero>
        <div className="stack" style={{ gap: 24 }}>
          <DocumentUploader />
          <div className="grid c3 stagger">
            {HOW.map(({ icon: Icon, title, text, g }) => (
              <Card key={title} hover>
                <div style={{ width: 44, height: 44, borderRadius: 14, display: "grid", placeItems: "center", color: "#fff", background: g, marginBottom: 12 }}>
                  <Icon size={22} />
                </div>
                <div style={{ fontWeight: 700, marginBottom: 4 }}>{title}</div>
                <div className="muted small">{text}</div>
              </Card>
            ))}
          </div>
        </div>
      </>
    );
  }

  /* -------------------------------- chat view ------------------------------- */
  return (
    <>
      <PageHero icon={<MessageSquare size={28} />} title="Chat">
        Ask questions about <b style={{ color: "var(--text)" }}>{doc.filename}</b>.
      </PageHero>

      <Card className="enter" style={{ marginBottom: 22 }}>
        <div className="grid c4">
          <Stat label="Document" value={doc.filename} small accent="violet" />
          <Stat label="Chunks" value={doc.n_chunks} accent="cyan" />
          <Stat label="Ingest time" value={ms(doc.duration_ms)} accent="warm" />
          <Stat label="Source" value={doc.from_cache ? "Cache" : "Fresh embed"} small accent="good" hint={doc.from_cache ? "Loaded instantly" : "Embedded just now"} />
        </div>
        <div className="row" style={{ marginTop: 14 }}>
          <Button size="sm" icon={<FileUp size={14} />} onClick={() => setShowUpload((s) => !s)}>{showUpload ? "Hide uploader" : "Upload different document"}</Button>
          {messages.length > 0 && (
            <Button size="sm" variant="ghost" icon={<Trash2 size={14} />} onClick={() => setMessages([])}>Clear conversation</Button>
          )}
        </div>
        {showUpload && <div style={{ marginTop: 14 }}><DocumentUploader compact onDone={() => setShowUpload(false)} /></div>}
      </Card>

      <div className="chat-wrap">
        {messages.length === 0 && !pending && (
          <Card className="enter">
            <div className="card-title"><span className="ic"><Sparkles size={16} /></span>Try asking</div>
            <p className="card-sub">Pick a starter or write your own below.</p>
            <div className="suggest">
              {SUGGESTIONS.map((s) => <button key={s} className="chip-btn" onClick={() => send(s)}>{s}</button>)}
            </div>
          </Card>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <div className="msg-user" key={m.id}>{m.content}</div>
          ) : (
            <div className="msg-bot" key={m.id}>
              <div className={`avatar ${m.mode === "agent" ? "agent" : ""}`}>{m.mode === "agent" ? <Bot size={19} /> : <Sparkles size={19} />}</div>
              <div className="bot-body">
                {m.error ? (
                  <div className="errbox"><div className="em">{m.error}</div></div>
                ) : m.rag ? (
                  <>
                    <RagAnswer rag={m.rag} />
                    <JudgePanel
                      rag={m.rag}
                      judge={m.judge}
                      ratingSaved={m.ratingSaved}
                      onJudge={(j) => patch(m.id, { judge: j })}
                      onSaved={() => patch(m.id, { ratingSaved: true })}
                    />
                  </>
                ) : m.agent ? (
                  <AgentAnswer agent={m.agent} />
                ) : null}
              </div>
            </div>
          ),
        )}

        {pending && (
          <div className="msg-bot">
            <div className={`avatar ${pending.mode === "agent" ? "agent" : ""}`}>{pending.mode === "agent" ? <Bot size={19} /> : <Sparkles size={19} />}</div>
            <div className="bot-body"><PendingAnswer mode={pending.mode} /></div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <textarea
            ref={taRef}
            rows={1}
            value={input}
            placeholder={agentMode ? "Ask the agent - it will call tools to search the document..." : "Ask a question about the document..."}
            onChange={(e) => {
              setInput(e.target.value);
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 140) + "px";
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <div className="row">
            <Toggle on={agentMode} onChange={setAgentMode} label={<span className="row" style={{ gap: 6 }}><Bot size={15} /> Ask the agent</span>} />
            {!agentMode && <Toggle on={useCache} onChange={setUseCache} label={<span className="row" style={{ gap: 6 }}><Zap size={15} /> Semantic cache</span>} />}
            {agentMode && <Badge kind="warning">Slower - makes several LLM calls</Badge>}
            <div className="spacer" />
            <Button variant="primary" icon={<Send size={16} />} loading={!!pending} disabled={!input.trim()} onClick={() => send()}>Send</Button>
          </div>
        </div>
      </div>
    </>
  );
}
