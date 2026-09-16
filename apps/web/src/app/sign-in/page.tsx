import { SignInForm } from "@/components/sign-in-form";

export default function SignInPage() {
  return (
    <main className="auth-shell">
      <section className="auth-panel" aria-labelledby="sign-in-title">
        <div className="wordmark" aria-label="ARGUS">ARGUS<span>·</span></div>
        <p className="eyebrow">Secure investigation environment</p>
        <h1 id="sign-in-title">Access control</h1>
        <p className="lede">Use your assigned credentials to enter the authorized workspace.</p>
        <SignInForm />
      </section>
      <aside className="auth-context" aria-label="System status">
        <div className="grid-mark" aria-hidden="true" />
        <p className="eyebrow">System posture</p>
        <p className="context-copy">Human-reviewed intelligence. Authorized access. Auditable actions.</p>
        <div className="status-line"><span /> Platform controls initializing</div>
      </aside>
    </main>
  );
}
