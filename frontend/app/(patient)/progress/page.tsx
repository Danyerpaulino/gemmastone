import PatientProgressPanel from "@/components/PatientProgressPanel";

export default function PatientProgressPage() {
    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Progress snapshot</h2>
                </div>
                <p className="muted">
                    This view pulls compliance logs from the backend (mock
                    nudges feed into these logs via webhooks). Use it to show
                    how engagement data closes the loop.
                </p>
            </div>

            <PatientProgressPanel />
        </section>
    );
}
