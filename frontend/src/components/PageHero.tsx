import { ReactNode } from "react";

export function PageHero({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <header className="hero enter">
      <div className="hero-icon">{icon}</div>
      <div>
        <h1>
          <span className="gradient-text">{title}</span>
        </h1>
        {children && <p>{children}</p>}
      </div>
    </header>
  );
}
