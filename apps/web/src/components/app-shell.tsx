"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { apiFetch, CurrentUser, getCurrentUser } from "@/lib/api";

const navigation = [
  { href: "/dashboard", label: "Overview", glyph: "◫" },
  { href: "/dashboard/documents", label: "Documents", glyph: "▣" },
  { href: "/dashboard/users", label: "Users", glyph: "◎" },
];

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>();
  const [error, setError] = useState("");

  useEffect(() => {
    getCurrentUser().then((result) => {
      if (!result) router.replace("/sign-in");
      setUser(result);
    }).catch(() => setError("Authentication service unavailable. Reload to try again."));
  }, [router]);

  async function logout() {
    try {
      const response = await apiFetch("/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error("Logout failed");
      sessionStorage.removeItem("argus_access_token");
      router.replace("/sign-in");
    } catch {
      setError("Sign-out could not be confirmed. Please try again when the service is available.");
    }
  }

  if (user === undefined) return <main className="app-loading" aria-live="polite">{error || "Verifying authorized access…"}</main>;
  if (user === null) return null;

  return <div className="workspace-shell">
    <a className="skip-link" href="#workspace-content">Skip to workspace content</a>
    <aside className="workspace-nav">
      <a className="workspace-wordmark" href="/dashboard">ARGUS<span>·</span></a>
      <p className="nav-label">Workspace</p>
      <nav aria-label="Primary navigation">
        {navigation.map((item) => <a key={item.href} href={item.href} className={pathname === item.href ? "nav-item active" : "nav-item"}><span aria-hidden="true">{item.glyph}</span>{item.label}</a>)}
      </nav>
      <div className="nav-footer">
        <div className="identity"><span className="identity-mark">{user.email.slice(0, 1).toUpperCase()}</span><span><strong>{user.email}</strong><small>{user.roles[0] ?? "Authorized user"}</small></span></div>
        <button className="text-button" onClick={logout}>Sign out</button>
      </div>
    </aside>
    <main id="workspace-content" className="workspace-main">{error && <p role="alert">{error}</p>}{children}</main>
  </div>;
}
