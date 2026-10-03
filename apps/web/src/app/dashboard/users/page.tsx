"use client";

import { useEffect, useState } from "react";

import { RevokeSessions } from "@/components/revoke-sessions";
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
    }).catch(() => setMessage("User records are currently unavailable. Reload to try again."));
  }, []);

  return <section className="dashboard" aria-labelledby="users-title">
    <header className="workspace-header"><div><p className="eyebrow">Access administration</p><h1 id="users-title">Users</h1><p>Review access and end active sessions. Account creation remains a controlled CLI operation. Revoking sessions does not disable an account.</p></div></header>
    {currentUser && <section className="security-strip" aria-label="Your sessions"><div><h2>Your sessions</h2><p>Sign out on all devices, including this one.</p></div><RevokeSessions email={currentUser.email} current /></section>}
    {message ? <p className="empty-message" role="status">{message}</p> : <div className="user-table" role="region" aria-label="Platform users" tabIndex={0}>
      <table className="admin-table"><thead><tr><th scope="col">User</th><th scope="col">Roles</th><th scope="col">Status</th><th scope="col">MFA</th><th scope="col">Sessions</th></tr></thead>
        <tbody>{users.map((user) => <tr key={user.id}><td><strong>{user.email}</strong>{user.id === currentUser?.id && <small>Current session</small>}</td><td>{user.roles.join(", ")}</td><td className={user.is_active ? "state-active" : "state-inactive"}>{user.is_active ? "Active" : "Inactive"}</td><td>{user.mfa_enabled ? "Enabled" : "Not enrolled"}</td><td>{user.id === currentUser?.id ? "Use your sessions above" : <RevokeSessions userId={user.id} email={user.email} />}</td></tr>)}</tbody>
      </table></div>}
  </section>;
}
