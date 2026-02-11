import Link from "next/link";

export default function HomePage() {
    return (
        <main className="page">
            <header className="hero">
                <div>
                    <p className="eyebrow">KidneyStones AI</p>
                    <h1>Voice-first kidney stone prevention</h1>
                    <p className="lead">
                        The prevention agent that calls, texts, and keeps patients
                        on track between visits. Powered by MedGemma context and
                        real-time voice AI.
                    </p>
                    <div className="actions">
                        <Link href="/login">
                            <button>Patient login</button>
                        </Link>
                        <Link className="ghost-link" href="/provider/dashboard">
                            Provider workspace
                        </Link>
                    </div>
                </div>
                <div className="hero-card">
                    <p className="eyebrow">What it does</p>
                    <ul className="list">
                        <li>Automated intake calls after clinic visits</li>
                        <li>SMS adherence reminders and two-way support</li>
                        <li>MedGemma-built prevention context updates</li>
                        <li>Compliance dashboard for providers</li>
                    </ul>
                </div>
            </header>

            <section className="grid">
                <div className="card">
                    <p className="eyebrow">For clinicians</p>
                    <h2>Compliance command center</h2>
                    <p className="muted">
                        Review adherence, trigger follow-ups, and monitor patient
                        engagement without extra staffing.
                    </p>
                    <div className="actions">
                        <Link href="/provider/dashboard">
                            <button>Open workspace</button>
                        </Link>
                        <Link className="text-link" href="/provider/settings">
                            Manage QR codes
                        </Link>
                    </div>
                </div>

                <div className="card">
                    <p className="eyebrow">For patients</p>
                    <h2>Prevention companion</h2>
                    <p className="muted">
                        A simple phone-first experience. No app required — just
                        calls, texts, and a personalized plan.
                    </p>
                    <div className="actions">
                        <Link href="/dashboard">
                            <button>Open companion</button>
                        </Link>
                        <Link className="text-link" href="/plan">
                            View plan
                        </Link>
                    </div>
                </div>
            </section>

            <section className="card">
                <h2>Architecture & technology</h2>
                <div className="info-list">
                    <div>
                        <span>Medical brain</span>
                        <strong>MedGemma context builder</strong>
                    </div>
                    <div>
                        <span>Voice agent</span>
                        <strong>Vapi + Telnyx</strong>
                    </div>
                    <div>
                        <span>Backend</span>
                        <strong>FastAPI + PostgreSQL</strong>
                    </div>
                    <div>
                        <span>Frontend</span>
                        <strong>Next.js (App Router)</strong>
                    </div>
                </div>
            </section>
        </main>
    );
}
