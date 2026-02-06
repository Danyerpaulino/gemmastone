import Link from "next/link";

import { fetchJson } from "@/lib/api";
import type { PatientList, StoneAnalysisList } from "@/lib/types";

const safeCount = (value: number | undefined) =>
    typeof value === "number" ? value : null;

export default async function ProviderDashboard() {
    const patients = await fetchJson<PatientList>("/patients?limit=6");
    const analyses = await fetchJson<StoneAnalysisList>("/analyses?limit=6");

    const patientCount = safeCount(patients.data?.total);
    const analysisCount = safeCount(analyses.data?.total);
    const latestAnalysis = analyses.data?.items?.[0];

    return (
        <section className="stack">
            <div className="stat-grid">
                <div className="stat-card">
                    <p className="eyebrow">Active patients</p>
    <h2>{patientCount ?? "—"}</h2>
                    <p className="stat-note">
                        Total patients on file for this provider.
                    </p>
                </div>
                <div className="stat-card">
                    <p className="eyebrow">Analyses run</p>
    <h2>{analysisCount ?? "—"}</h2>
                    <p className="stat-note">
                        Workflow runs across all uploaded CT scans.
                    </p>
                </div>
                <div className="stat-card">
                    <p className="eyebrow">Latest urgency</p>
                    <h2>{latestAnalysis?.urgency_level || "Routine"}</h2>
                    <p className="stat-note">
                        Most recent analysis urgency signal.
                    </p>
                </div>
            </div>

            <div className="grid">
                <div className="card">
                    <div className="card-header">
                        <h2>Latest analysis</h2>
                        <Link className="text-link" href="/patients">
                            View all patients
                        </Link>
                    </div>
                    {latestAnalysis ? (
                        <div className="info-list">
                            <div>
                                <span>Patient ID</span>
                                <strong>{latestAnalysis.patient_id}</strong>
                            </div>
                            <div>
                                <span>Treatment</span>
                                <strong>
                                    {latestAnalysis.treatment_recommendation ||
                                        "Pending"}
                                </strong>
                            </div>
                            <div>
                                <span>Composition</span>
                                <strong>
                                    {latestAnalysis.predicted_composition ||
                                        "Unknown"}
                                </strong>
                            </div>
                            <div>
                                <span>Provider approval</span>
                                <strong>
                                    {latestAnalysis.provider_approved
                                        ? "Approved"
                                        : "Needs review"}
                                </strong>
                            </div>
                        </div>
                    ) : (
                        <p className="empty">
                            No analyses yet. Run a CT intake to begin.
                        </p>
                    )}
                </div>
                <div className="card">
                    <div className="card-header">
                        <h2>Quick actions</h2>
                    </div>
                    <div className="action-grid">
                        <Link className="action-card" href="/upload">
                            <h3>Run CT intake</h3>
                            <p>
                                Upload a scan, attach labs, and generate the
                                workflow outputs.
                            </p>
                        </Link>
                        <Link className="action-card" href="/patients">
                            <h3>Review patients</h3>
                            <p>
                                Check latest analyses and open plans awaiting
                                approval.
                            </p>
                        </Link>
                    </div>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>Recent patients</h2>
                    <Link className="text-link" href="/patients">
                        All patients
                    </Link>
                </div>
                {patients.data?.items?.length ? (
                    <div className="table compact">
                        <div className="table-head">
                            <span>Name</span>
                            <span>Email</span>
                            <span>Phone</span>
                            <span></span>
                        </div>
                        {patients.data.items.map((patient) => (
                            <div className="table-row" key={patient.id}>
                                <span>
                                    {patient.first_name} {patient.last_name}
                                </span>
                                <span>{patient.email || "—"}</span>
                                <span>{patient.phone || "—"}</span>
                                <Link
                                    className="text-link"
                                    href={`/patients/${patient.id}`}
                                >
                                    Open
                                </Link>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="empty">
                        {patients.error
                            ? `Unable to load patients: ${patients.error}`
                            : "No patients found yet."}
                    </p>
                )}
            </div>
        </section>
    );
}
