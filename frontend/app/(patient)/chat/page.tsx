import PatientChatPanel from "@/components/PatientChatPanel";

export default function PatientChatPage() {
    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Chat with your care assistant</h2>
                </div>
                <p className="muted">
                    This chat uses MedGemma to explain your plan and answer
                    questions in plain language. If you report emergency
                    symptoms, it will advise you to contact your care team.
                </p>
            </div>
            <PatientChatPanel />
        </section>
    );
}
