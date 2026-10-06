import { ReactNode, CSSProperties } from "react";

interface Props {
  title?: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  glow?: boolean;
  hover?: boolean;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

export function Card({ title, subtitle, icon, action, glow, hover, className = "", style, children }: Props) {
  return (
    <section className={`card ${glow ? "glow" : ""} ${hover ? "hover" : ""} ${className}`} style={style}>
      {(title || action) && (
        <div className="row" style={{ alignItems: "flex-start", flexWrap: "nowrap" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            {title && (
              <div className="card-title">
                {icon && <span className="ic">{icon}</span>}
                {title}
              </div>
            )}
            {subtitle && <p className="card-sub">{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
