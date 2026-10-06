import { createContext, ReactNode, useCallback, useContext, useState } from "react";
import { CheckCircle2, AlertTriangle, Info, X } from "lucide-react";

type Kind = "success" | "error" | "info";
interface T {
  id: number;
  kind: Kind;
  title: string;
  message?: string;
  leaving?: boolean;
}
interface Ctx {
  toast: (kind: Kind, title: string, message?: string) => void;
}

const ToastCtx = createContext<Ctx>({ toast: () => {} });
export const useToast = () => useContext(ToastCtx);

let counter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<T[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((xs) => xs.map((x) => (x.id === id ? { ...x, leaving: true } : x)));
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 260);
  }, []);

  const toast = useCallback(
    (kind: Kind, title: string, message?: string) => {
      const id = ++counter;
      setItems((xs) => [...xs.slice(-4), { id, kind, title, message }]);
      setTimeout(() => dismiss(id), 4500);
    },
    [dismiss],
  );

  return (
    <ToastCtx.Provider value={{ toast }}>
      {children}
      <div className="toasts" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.kind} ${t.leaving ? "leaving" : ""}`}>
            <span className="ti">{t.kind === "success" ? <CheckCircle2 size={18} /> : t.kind === "error" ? <AlertTriangle size={18} /> : <Info size={18} />}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="tt">{t.title}</div>
              {t.message && <div className="tm">{t.message}</div>}
            </div>
            <button className="btn ghost icon sm" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              <X size={14} />
            </button>
            <span className="bar" />
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
