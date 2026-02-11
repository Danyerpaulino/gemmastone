import Link from "next/link";

import LatestPlanPreview from "@/components/LatestPlanPreview";
import LatestRunPanel from "@/components/LatestRunPanel";

export default async function PatientPlanPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Prevention plan review</h2>
                    <Link className="text-link" href={`/provider/patients/${id}`}>
                        Patient overview
                    </Link>
                </div>
                <p className="muted">
                    Approve the AI-generated plan after clinical validation.
                    Approval unlocks mock engagement nudges.
                </p>
            </div>

            <div className="grid">
                <LatestPlanPreview patientId={id} />
                <LatestRunPanel patientId={id} />
            </div>
        </section>
    );
}
