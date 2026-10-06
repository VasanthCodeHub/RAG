import { ReactNode } from "react";

export type BadgeKind = "success" | "warning" | "danger" | "info" | "violet" | "neutral";

export function Badge({ kind = "neutral", dot, pulse, children }: { kind?: BadgeKind; dot?: boolean; pulse?: boolean; children: ReactNode }) {
  return (
    <span className={`badge ${kind}`}>
      {dot && <span className={`dot ${pulse ? "pulse" : ""}`} />}
      {children}
    </span>
  );
}
