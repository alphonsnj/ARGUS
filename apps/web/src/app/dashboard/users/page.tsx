"use client";

import { useEffect, useState } from "react";

import { apiFetch, CurrentUser, getCurrentUser } from "@/lib/api";

export default function UsersPage() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [users, setUsers] = useState<CurrentUser[]>([]);
  const [message, setMessage] = useState("Loading user boundary…");

  useEffect(() => {
    getCurrentUser().then(async (user) => {
      setCurrentUser(user);
      if (!user) return;
      const response = await apiFetch("/users");
      if (response.ok) { setUsers(await response.json()); setMessage(""); }
      else if (response.status === 403) setMessage("Your role can view your profile but cannot list platform users.");
      else setMessage("User records are currently unavailable.");
    });
  }, []);

  return <section className="dashboard" aria-labelledby="users-title">
    <header className="workspace-header"><div><p className="eyebrow">Access administration</p><h1 id="users-title">Users</h1><p>User creation remains a controlled CLI operation in this foundation release. This page is read-only by design.</p></div></header>
    {message ? <p className="empty-message" role="status">{message}</p> : <div className="user-table" role="region" aria-label="Platform users" tabIndex={0}><div className="table-row table-head"><span>User</span><span>Roles</span><span>Status</span><span>MFA</span></div>{users.map((user) => <div className="table-row" key={user.id}><span><strong>{user.email}</strong>{user.id === currentUser?.id && <small>Current session</small>}</span><span>{user.roles.join(", ")}</span><span className={user.is_active ? "state-active" : "state-inactive"}>{user.is_active ? "Active" : "Inactive"}</span><span>{user.mfa_enabled ? "Enabled" : "Not enrolled"}</span></div>)}</div>}
  </section>;
}
