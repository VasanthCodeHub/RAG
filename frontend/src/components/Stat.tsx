import { ReactNode, CSSProperties } from "react";

const ACCENTS: Record<string, string> = {
  violet: "var(--grad)",
  cyan: "var(--grad-cool)",
  good: "var(--grad-good)",
  warm: "var(--grad-warm)",
};

export function Stat({ label, value, hint, icon, accent = "violet", small, delay = 0 }: {
  label: ReactNode;
  value: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  accent?: string;
  small?: boolean;
  delay?: number;
}) {
  const style = { "--accent": ACCENTS[accent] ?? accent, animationDelay: `${delay}ms` } as CSSProperties;
  return (
    <div className="stat" style={style}>
      <div className="l">{icon}{label}</div>
      <div className={`v ${small ? "sm" : ""}`}>{value}</div>
      {hint && <div className="h">{hint}</div>}
    </div>
  );
}
