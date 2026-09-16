"use client";

import { useEffect, useState } from "react";

import { CurrentUser, getCurrentUser } from "@/lib/api";

export default function DashboardPage() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  useEffect(() => { getCurrentUser().then(setUser); }, []);

  return <section className="dashboard" aria-labelledby="overview-title">
    <header className="workspace-header"><div><p className="eyebrow">Authorized workspace</p><h1 id="overview-title">Operational overview</h1><p>ARGUS is ready for approved investigation workflows. No case or evidence data has been introduced.</p></div><span className="secure-pill"><i /> System secure</span></header>
    <div className="foundation-grid">
      <section className="foundation-card primary"><p className="card-kicker">Your access</p><h2>{user?.roles[0] ?? "Authorized user"}</h2><p>Signed in as {user?.email ?? "…"}. Permissions are evaluated by the API for every protected request.</p><a className="inline-action" href="/dashboard/users">Review user access →</a></section>
      <section className="foundation-card"><p className="card-kicker">Investigation data</p><h2>Not yet introduced</h2><p>Cases, persons, evidence, and search records remain intentionally unavailable until their approved implementation increments.</p></section>
      <section className="foundation-card"><p className="card-kicker">Control state</p><ul className="status-list"><li><span /> Identity verified</li><li><span /> Session protected</li><li><span /> Audit-ready foundation</li></ul></section>
    </div>
    <section className="readiness-panel"><div><p className="card-kicker">Platform readiness</p><h2>Foundation controls are online.</h2></div><p>The dashboard is intentionally data-free. It will surface only authorized, indexed records when their modules are implemented.</p></section>
  </section>;
}
