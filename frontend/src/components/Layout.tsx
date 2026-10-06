import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { MessageSquare, FlaskConical, Bot, Plug, Users, Activity, Sun, Moon, Menu, FileText, KeyRound, Eye, EyeOff, FileX, Layers } from "lucide-react";
import { useApp } from "../context/AppContext";
import { Badge } from "./Badge";
import { Button } from "./Button";
import { useToast } from "./Toast";

const NAV = [
  { to: "/", label: "Chat", icon: MessageSquare },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/mcp", label: "MCP Explorer", icon: Plug },
  { to: "/a2a", label: "A2A Team", icon: Users },
  { to: "/observability", label: "Observability", icon: Activity },
];

export function HealthChip() {
  const { health, healthError, refreshHealth } = useApp();
  if (healthError) return <span onClick={refreshHealth} style={{ cursor: "pointer" }}><Badge kind="danger" dot>API offline</Badge></span>;
  if (!health) return <Badge kind="neutral" dot pulse>Connecting...</Badge>;
  return (
    <span style={{ display: "inline-flex", gap: 8 }}>
      <Badge kind="success" dot pulse>API {health.status}</Badge>
      <Badge kind={health.groq_key_configured ? "info" : "warning"}>{health.groq_key_configured ? "Server Groq key" : "No server key"}</Badge>
    </span>
  );
}

function KeyField() {
  const { apiKey, setApiKey } = useApp();
  const [show, setShow] = useState(false);
  return (
    <div className="field">
      <label><KeyRound size={13} /> Groq API key</label>
      <div style={{ position: "relative" }}>
        <input
          className="input"
          style={{ paddingRight: 38, fontSize: "0.82rem" }}
          type={show ? "text" : "password"}
          value={apiKey}
          placeholder="blank = use server key"
          onChange={(e) => setApiKey(e.target.value.trim())}
          autoComplete="off"
        />
        <button className="btn ghost icon sm" style={{ position: "absolute", right: 3, top: 3, padding: 6 }} onClick={() => setShow(!show)} aria-label="Toggle visibility">
          {show ? <EyeOff size={14} /> : <Eye size={14} />}
        </button>
      </div>
      <span className="hint">Optional. Stored in this browser only.</span>
    </div>
  );
}

export function Layout() {
  const { doc, setDoc, theme, toggleTheme } = useApp();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const loc = useLocation();

  return (
    <>
      <div className="aurora"><span /><span /><span /></div>
      <div className="shell">
        <aside className={`sidebar ${open ? "open" : ""}`} onClick={() => setOpen(false)}>
          <div className="brand">
            <div className="brand-logo"><Layers size={22} /></div>
            <div>
              <div className="brand-name gradient-text">Simple RAG</div>
              <div className="brand-sub">Ask anything. Inspect everything.</div>
            </div>
          </div>
          <div className="nav-label">Workspace</div>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} end={to === "/"} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
          <div className="sidebar-foot" onClick={(e) => e.stopPropagation()}>
            {doc ? (
              <div className="doc-pill enter">
                <FileText size={20} style={{ color: "var(--cyan)", flexShrink: 0 }} />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div className="t" title={doc.filename}>{doc.filename}</div>
                  <div className="s">{doc.n_chunks} chunks - {doc.pdf_hash.slice(0, 8)}</div>
                </div>
                <button className="btn ghost icon sm" title="Forget document" onClick={() => { setDoc(null); toast("info", "Document cleared"); }}><FileX size={14} /></button>
              </div>
            ) : (
              <div className="doc-pill faint">No active document</div>
            )}
            <KeyField />
          </div>
        </aside>

        <div className="main">
          <div className="topbar">
            <Button variant="ghost" size="icon" className="menu-btn" onClick={() => setOpen(true)} aria-label="Menu"><Menu size={20} /></Button>
            <HealthChip />
            <div className="grow" />
            {doc && <Badge kind="violet"><FileText size={12} /> {doc.filename}</Badge>}
            <Button variant="ghost" size="icon" onClick={toggleTheme} aria-label="Toggle theme" title="Toggle light/dark">
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          </div>
          <main className="page" key={loc.pathname}>
            <Outlet />
          </main>
        </div>
      </div>
    </>
  );
}
