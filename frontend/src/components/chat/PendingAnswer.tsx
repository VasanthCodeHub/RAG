import { useEffect, useState } from "react";
import { PipelineSteps, RAG_STEPS, Thinking, Skeleton } from "..";

/** Animated placeholder shown while the backend works. Steps advance on a timer and hold on the last one. */
export function PendingAnswer({ mode }: { mode: "rag" | "agent" }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timers = [250, 800, 1400].map((t, i) => setTimeout(() => setStep(i + 1), t));
    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="stack" style={{ gap: 14 }}>
      {mode === "rag" ? (
        <PipelineSteps steps={RAG_STEPS} current={step} />
      ) : (
        <div className="row small muted">
          <Thinking /> The agent is deciding which tool to call...
        </div>
      )}
      <div className="answer stack" style={{ gap: 10 }}>
        <Skeleton h={14} w="92%" />
        <Skeleton h={14} w="78%" />
        <Skeleton h={14} w="55%" />
      </div>
    </div>
  );
}
