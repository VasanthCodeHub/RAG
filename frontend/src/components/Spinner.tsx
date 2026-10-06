import { CSSProperties } from "react";

export function Spinner({ large }: { large?: boolean }) {
  return <span className={`spinner ${large ? "lg" : ""}`} role="status" aria-label="Loading" />;
}

export function Skeleton({ h = 16, w = "100%", style }: { h?: number | string; w?: number | string; style?: CSSProperties }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />;
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <Skeleton h={20} w="40%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} h={14} w={`${95 - i * 12}%`} />
      ))}
    </div>
  );
}

export function SkeletonStats({ n = 4 }: { n?: number }) {
  return (
    <div className="grid" style={{ gridTemplateColumns: `repeat(${n}, minmax(0,1fr))` }}>
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} h={78} style={{ borderRadius: 14 }} />
      ))}
    </div>
  );
}

export function Thinking() {
  return (
    <span className="thinking">
      <i />
      <i />
      <i />
    </span>
  );
}
