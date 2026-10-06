import { ReactNode } from "react";
import { AlertTriangle, Inbox, Info, FileQuestion } from "lucide-react";
import { Button } from "./Button";

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="empty enter">
      <div className="ei">{icon ?? <Inbox size={28} />}</div>
      <h3>{title}</h3>
      {children && <div className="small" style={{ maxWidth: 480, margin: "0 auto" }}>{children}</div>}
      {action && <div style={{ marginTop: 16 }}>{action}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="errbox" role="alert">
      <AlertTriangle size={20} style={{ flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, marginBottom: 2 }}>Something went wrong</div>
        <div className="em">{error}</div>
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  );
}

export function Notice({ kind = "warning", children }: { kind?: "warning" | "info" | "good"; children: ReactNode }) {
  return (
    <div className={`notice ${kind === "warning" ? "" : kind}`}>
      <Info size={18} style={{ flexShrink: 0, marginTop: 2 }} />
      <div className="nm">{children}</div>
    </div>
  );
}

export function NoDocument({ action }: { action?: ReactNode }) {
  return (
    <EmptyState icon={<FileQuestion size={28} />} title="No active document" action={action}>
      Upload a document on the Chat page first. It becomes the active document shared by every page.
    </EmptyState>
  );
}
