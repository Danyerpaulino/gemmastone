import Link from "next/link";

import LatestRunPanel from "@/components/LatestRunPanel";
import StoneMeshViewer from "@/components/StoneMeshViewer";
import { fetchJson } from "@/lib/api";
import type { StoneAnalysisList } from "@/lib/types";

export default async function PatientAnalysisPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    const analyses = await fetchJson<StoneAnalysisList>(
        `/analyses/?patient_id=${id}&limit=5`
    );
    const latest = analyses.data?.items?.[0];

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Analysis review</h2>
                    <Link className="text-link" href={`/patients/${id}`}>
                        Patient overview
                    </Link>
                </div>
                <p className="muted">
                    Review the latest AI findings. Approve the plan once it has
                    been clinically validated.
                </p>
            </div>

            <div className="grid">
                <div className="card">
                    <div className="card-header">
                        <h2>Latest analysis (API)</h2>
                    </div>
                    {latest ? (
                        <div className="info-list">
                            <div>
                                <span>Composition</span>
                                <strong>
                                    {latest.predicted_composition || "Unknown"}
                                </strong>
                            </div>
                            <div>
                                <span>Treatment</span>
                                <strong>
                                    {latest.treatment_recommendation ||
                                        "Pending"}
                                </strong>
                            </div>
                            <div>
                                <span>Urgency</span>
                                <strong>{latest.urgency_level || "Routine"}</strong>
                            </div>
                            <div>
                                <span>Hydronephrosis</span>
                                <strong>
                                    {latest.hydronephrosis_level || "None"}
                                </strong>
                            </div>
                        </div>
                    ) : (
                        <p className="empty">
                            {analyses.error
                                ? `Unable to load analyses: ${analyses.error}`
                                : "No analyses found yet."}
                        </p>
                    )}
                </div>

                <LatestRunPanel patientId={id} />
                <StoneMeshViewer analysisId={latest?.id} />
            </div>
        </section>
    );
}
