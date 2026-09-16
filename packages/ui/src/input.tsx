import { forwardRef, useId } from "react";
import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string };

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({ label, error, id, ...props }, ref) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return <label className="field" htmlFor={inputId}><span>{label}</span><input id={inputId} ref={ref} aria-invalid={Boolean(error)} aria-describedby={error ? `${inputId}-error` : undefined} {...props} />{error && <small id={`${inputId}-error`}>{error}</small>}</label>;
});
