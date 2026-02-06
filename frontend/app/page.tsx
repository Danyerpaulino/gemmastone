import Link from "next/link";

export default function HomePage() {
    return (
        <main className="page">
            <header className="hero">
                <div>
                    <p className="eyebrow">MedGemma Impact Challenge</p>
                    <h1>KidneyStone AI</h1>
                    <p className="lead">
                        Agentic workflows for kidney stone imaging, treatment
                        planning, and patient support.
                    </p>
                </div>
                <div className="hero-card">
                    <p className="hero-title">About this demo</p>
                    <p>
                        This application demonstrates an end-to-end workflow
                        using <strong>MedGemma</strong> and{" "}
                        <strong>LangGraph</strong> to analyze CT scans, generate
                        prevention plans, and support patients via a
                        conversational agent.
                    </p>
                </div>
            </header>

            <section className="grid">
                <div className="card">
                    <p className="eyebrow">For Clinicians</p>
                    <h2>Provider Portal</h2>
                    <p className="muted">
                        Access the clinical command center to upload CT scans,
                        review AI-generated analyses, approve treatment plans,
                        and monitor patient adherence.
                    </p>
                    <div className="actions">
                        <Link href="/dashboard">
                            <button>Open Workspace</button>
                        </Link>
                        <Link className="text-link" href="/upload">
                            Run Quick Intake
                        </Link>
                    </div>
                </div>

                <div className="card">
                    <p className="eyebrow">For Patients</p>
                    <h2>Patient Companion</h2>
                    <p className="muted">
                        Engage with your personalized care assistant. Chat about
                        your diagnosis, view your hydration goals, and track
                        your daily progress.
                    </p>
                    <div className="actions">
                        <Link href="/chat">
                            <button>Start Chat</button>
                        </Link>
                        <Link className="text-link" href="/my-plan">
                            View Plan
                        </Link>
                    </div>
                </div>
            </section>

            <section className="card">
                <h2>Architecture & Technology</h2>
                <div className="info-list">
                    <div>
                        <span>Backend</span>
                        <strong>FastAPI + LangGraph</strong>
                    </div>
                    <div>
                        <span>LLM Integration</span>
                        <strong>MedGemma (Google)</strong>
                    </div>
                    <div>
                        <span>Frontend</span>
                        <strong>Next.js (App Router)</strong>
                    </div>
                    <div>
                        <span>Database</span>
                        <strong>PostgreSQL (AsyncPG)</strong>
                    </div>
                </div>
            </section>
        </main>
    );
}
