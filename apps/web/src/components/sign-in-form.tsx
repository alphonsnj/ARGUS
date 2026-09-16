"use client";

import { Button, Input } from "@argus/ui";
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

const signInSchema = z.object({ email: z.string().email(), password: z.string().min(12).max(128) });
type SignInValues = z.infer<typeof signInSchema>;

export function SignInForm() {
  const [message, setMessage] = useState<string>();
  const [authenticated, setAuthenticated] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<SignInValues>({ resolver: zodResolver(signInSchema) });

  async function onSubmit(values: SignInValues) {
    setMessage(undefined);
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/auth/token`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(values),
          credentials: "include",
        },
      );
      if (!response.ok) {
        setMessage("Access could not be verified. Check your credentials or contact an administrator.");
        return;
      }
      const payload: { access_token: string } = await response.json();
      sessionStorage.setItem("argus_access_token", payload.access_token);
      setAuthenticated(true);
      setMessage("Access verified. Opening the workspace…");
      window.location.assign("/dashboard");
    } catch {
      setMessage("ARGUS could not reach the authentication service. Try again shortly.");
    }
  }

  return <form className="auth-form" onSubmit={handleSubmit(onSubmit)} noValidate>
    <Input label="Work email" autoComplete="email" error={errors.email?.message} {...register("email")} />
    <Input label="Password" type="password" autoComplete="current-password" error={errors.password?.message} {...register("password")} />
    {message && <p className={authenticated ? "form-success" : "form-error"} role="status">{message}</p>}
    <Button type="submit" loading={isSubmitting} disabled={authenticated}>{authenticated ? "Access verified" : "Verify access"}</Button>
  </form>;
}
