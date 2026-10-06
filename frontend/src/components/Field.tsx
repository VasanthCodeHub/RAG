import { ReactNode } from "react";

export function Field({ label, hint, children }: { label: ReactNode; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: ReactNode }) {
  return (
    <span
      className={`toggle ${on ? "on" : ""}`}
      role="switch"
      aria-checked={on}
      tabIndex={0}
      onClick={() => onChange(!on)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onChange(!on);
        }
      }}
    >
      <span className="track" />
      {label}
    </span>
  );
}

export function Stars({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <span className="stars">
      {[1, 2, 3, 4, 5].map((n) => (
        <button type="button" key={n} className={n <= value ? "on" : ""} onClick={() => onChange(n)} aria-label={`${n} stars`}>
          <svg width="22" height="22" viewBox="0 0 24 24" fill={n <= value ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
            <path d="M12 2l3 7 7 .6-5.3 4.8 1.6 7.1L12 17.8 5.7 21.5l1.6-7.1L2 9.6 9 9z" />
          </svg>
        </button>
      ))}
    </span>
  );
}
