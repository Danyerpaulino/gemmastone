import PatientPlanWorkspace from "@/components/PatientPlanWorkspace";

export default function PatientPlanPage() {
    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>My prevention plan</h2>
                </div>
                <p className="muted">
                    Your plan is personalized based on imaging and labs. This
                    demo pulls the latest plan directly from the API.
                </p>
            </div>
            <PatientPlanWorkspace />
        </section>
    );
}
