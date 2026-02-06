import Link from "next/link";

import { fetchJson } from "@/lib/api";
import type { PatientOut, StoneAnalysisList } from "@/lib/types";

export default async function PatientDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    const patient = await fetchJson<PatientOut>(`/patients/${id}`);
    const analyses = await fetchJson<StoneAnalysisList>(
        `/analyses?patient_id=${id}&limit=5`
    );

    const latest = analyses.data?.items?.[0];

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Patient overview</h2>
                    <Link className="text-link" href="/patients">
                        Back to list
                    </Link>
                </div>
                {patient.data ? (
                    <div className="info-list">
                        <div>
                            <span>Name</span>
                            <strong>
                                {patient.data.first_name} {patient.data.last_name}
                            </strong>
                        </div>
                        <div>
                            <span>MRN</span>
                            <strong>{patient.data.mrn || "—"}</strong>
                        </div>
                        <div>
                            <span>Email</span>
                            <strong>{patient.data.email || "—"}</strong>
                        </div>
                        <div>
                            <span>Phone</span>
                            <strong>{patient.data.phone || "—"}</strong>
                        </div>
                    </div>
                ) : (
                    <p className="empty">
                        {patient.error
                            ? `Unable to load patient: ${patient.error}`
                            : "Patient not found."}
                    </p>
                )}
            </div>

            <div className="grid">
                <div className="card">
                    <div className="card-header">
                        <h2>Latest analysis</h2>
                        <Link
                            className="text-link"
                            href={`/patients/${id}/analysis`}
                        >
                            Open analysis
                        </Link>
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
                                <span>Approved</span>
                                <strong>
                                    {latest.provider_approved
                                        ? "Yes"
                                        : "Needs review"}
                                </strong>
                            </div>
                        </div>
                    ) : (
                        <p className="empty">No analysis history yet.</p>
                    )}
                </div>
                <div className="card">
                    <div className="card-header">
                        <h2>Plan workspace</h2>
                        <Link
                            className="text-link"
                            href={`/patients/${id}/plan`}
                        >
                            Review plan
                        </Link>
                    </div>
                    <p className="muted">
                        Use the plan review page to approve the AI-generated
                        prevention plan once you have verified accuracy.
                    </p>
                    <div className="pill">
                        Plan approval gates mock nudges and engagement.
                    </div>
                </div>
                <div className="card">
                    <div className="card-header">
                        <h2>Compliance logs</h2>
                        <Link
                            className="text-link"
                            href={`/patients/${id}/compliance`}
                        >
                            View compliance
                        </Link>
                    </div>
                    <p className="muted">
                        Review hydration and adherence data captured from mock
                        engagement responses.
                    </p>
                </div>
            </div>
        </section>
    );
}
