"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";

type AuditEvent = {
  id: string; created_at: string; action: string;
  actor_id: string | null; subject_id: string | null; request_id: string | null;
};

export default function AuditPage() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [busy, setBusy] = useState(true);
  const [message, setMessage] = useState("");
  const [loaded, setLoaded] = useState(false);
  const load = useCallback(async () => {
    setBusy(true);
    setMessage("");
    try {
      const response = await apiFetch("/audit?limit=100");
      if (!response.ok) {
        setEvents([]);
        setLoaded(false);
        setMessage(response.status === 403 ? "Audit history is restricted to Super Administrators." : "Audit history is unavailable. Try refreshing.");
        return;
      }
      setEvents(await response.json());
      setLoaded(true);
    } catch { setMessage("Audit history could not be refreshed. Check the connection and try again."); }
    finally { setBusy(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  return <section className="dashboard" aria-labelledby="audit-title">
    <header className="workspace-header"><div><p className="eyebrow">Accountability</p><h1 id="audit-title">Audit history</h1><p>The latest 100 recorded events, newest first. This view is read-only; viewing it is also recorded. Times are shown in UTC.</p></div><button className="control-button" disabled={busy} onClick={() => void load()}>{busy ? "Loading…" : "Refresh history"}</button></header>
    <p role="status" className={message ? "form-error admin-status" : "admin-status"}>{message || (busy ? "Loading audit history…" : loaded ? `${events.length} events loaded.` : "")}</p>
    {loaded && !events.length && <p className="empty-message">No recorded events.</p>}
    {!!events.length && <div className="user-table" role="region" aria-label="Recorded audit events" tabIndex={0} aria-busy={busy}>
      <table className="admin-table audit-table"><thead><tr><th scope="col">Time (UTC)</th><th scope="col">Action</th><th scope="col">Actor ID</th><th scope="col">Subject ID</th><th scope="col">Request ID</th></tr></thead><tbody>
        {events.map(event => <tr key={event.id}><td><time dateTime={event.created_at}>{new Date(event.created_at).toISOString().replace("T", " ").replace("Z", " UTC")}</time></td><td><strong>{event.action}</strong></td><td><code>{event.actor_id ?? "System / anonymous"}</code></td><td><code>{event.subject_id ?? "—"}</code></td><td><code>{event.request_id ?? "—"}</code></td></tr>)}
      </tbody></table></div>}
  </section>;
}
