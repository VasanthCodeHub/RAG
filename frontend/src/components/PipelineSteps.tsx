import { Check, Search, ArrowDownUp, Sparkles, MessageSquare, FileText, Scissors } from "lucide-react";
import { ReactNode } from "react";

export interface PStep {
  label: string;
  icon?: ReactNode;
  duration?: number | null;
}

export const RAG_STEPS: PStep[] = [
  { label: "Question", icon: <MessageSquare size={16} /> },
  { label: "Retrieve", icon: <Search size={16} /> },
  { label: "Rerank", icon: <ArrowDownUp size={16} /> },
  { label: "Generate", icon: <Sparkles size={16} /> },
];

export const INGEST_STEPS: PStep[] = [
  { label: "Upload", icon: <FileText size={16} /> },
  { label: "Parse", icon: <Search size={16} /> },
  { label: "Chunk", icon: <Scissors size={16} /> },
  { label: "Embed", icon: <Sparkles size={16} /> },
];

/** `current` = index of the running step; steps before it are done. current >= steps.length means all done. */
export function PipelineSteps({ steps, current }: { steps: PStep[]; current: number }) {
  return (
    <div className="pipeline">
      {steps.map((s, i) => {
        const state = i < current ? "done" : i === current ? "active" : "";
        return (
          <div key={s.label} className={`pstep ${state}`}>
            <div className="pdot">{state === "done" ? <Check size={17} strokeWidth={3} /> : s.icon}</div>
            <div className="plabel">{s.label}</div>
            <div className="pdur">{s.duration != null && state === "done" ? `${Math.round(s.duration)} ms` : state === "active" ? "running..." : ""}</div>
          </div>
        );
      })}
    </div>
  );
}
