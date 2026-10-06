import { ChevronRight, Wrench, OctagonX } from "lucide-react";
import { ToolLogEntry } from "../api/client";

export function ToolSteps({ tools, blocked }: { tools: (string | ToolLogEntry)[]; blocked?: string | null }) {
  if (!tools.length && !blocked) return <span className="faint small">no tool calls</span>;
  return (
    <div className="tsteps">
      {tools.map((t, i) => {
        const name = typeof t === "string" ? t : t.tool;
        const err = typeof t !== "string" && t.error;
        return (
          <span key={i} style={{ display: "contents" }}>
            {i > 0 && <ChevronRight size={14} className="tarrow" />}
            <span className={`tstep ${err ? "error" : ""}`} style={{ animationDelay: `${i * 70}ms` }}>
              <Wrench size={12} /> {name}
            </span>
          </span>
        );
      })}
      {blocked && (
        <>
          <ChevronRight size={14} className="tarrow" />
          <span className="tstep blocked" style={{ animationDelay: `${tools.length * 70}ms` }}>
            <OctagonX size={12} /> {blocked}
          </span>
        </>
      )}
    </div>
  );
}
