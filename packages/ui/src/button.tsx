import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean };

export function Button({ children, className = "", loading = false, disabled, ...props }: ButtonProps) {
  return <button className={`button ${className}`} disabled={disabled || loading} {...props}>{loading ? "Verifying…" : children}</button>;
}
