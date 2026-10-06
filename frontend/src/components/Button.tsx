import { ButtonHTMLAttributes, ReactNode } from "react";
import { Spinner } from "./Spinner";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "default" | "ghost" | "danger";
  size?: "md" | "sm" | "icon";
  loading?: boolean;
  icon?: ReactNode;
}

export function Button({ variant = "default", size = "md", loading, icon, children, className = "", disabled, ...rest }: Props) {
  const v = variant === "default" ? "" : variant;
  const s = size === "md" ? "" : size;
  return (
    <button className={`btn ${v} ${s} ${className}`} disabled={disabled || loading} {...rest}>
      {loading ? <Spinner /> : icon}
      {children}
    </button>
  );
}
