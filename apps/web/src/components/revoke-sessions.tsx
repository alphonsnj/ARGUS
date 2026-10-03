"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { apiFetch } from "@/lib/api";

export function RevokeSessions({ userId, email, current = false }: {
  userId?: string; email: string; current?: boolean;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  async function revoke() {
    const description = current ? "your account (including this session)" : email;
    if (!window.confirm(`Sign out all sessions for ${description}? This does not disable the account or prevent a new login.`)) return;
    setBusy(true);
    setMessage("");
    setFailed(false);
    try {
      const response = await apiFetch(userId ? `/users/${encodeURIComponent(userId)}/sessions` : "/auth/logout-all", {
        method: userId ? "DELETE" : "POST",
      });
      if (!response.ok) {
        setFailed(true);
        setMessage(response.status === 403 ? "Only Super Administrators can revoke another user's sessions." : "Sign-out could not be confirmed. Please try again.");
        return;
      }
      if (current) {
        sessionStorage.removeItem("argus_access_token");
        router.replace("/sign-in");
      } else setMessage(`Sessions revoked for ${email}. A new login is still allowed.`);
    } catch {
      setFailed(true);
      setMessage("Service unavailable. Sign-out could not be confirmed.");
    } finally { setBusy(false); }
  }

  return <div className="session-action">
    <button className="control-button" disabled={busy} onClick={revoke}
      aria-label={current ? "Sign out everywhere" : `Revoke sessions for ${email}`}>
      {busy ? "Revoking…" : current ? "Sign out everywhere" : "Revoke sessions"}
    </button>
    <p className={failed ? "form-error" : "form-success"} role="status">{message}</p>
  </div>;
}
