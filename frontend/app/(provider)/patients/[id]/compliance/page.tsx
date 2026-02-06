import Link from "next/link";

import { fetchJson } from "@/lib/api";
import type { ComplianceLogList } from "@/lib/types";

const formatDate = (value: string) => {
    try {
        return new Date(value).toLocaleDateString();
    } catch (error) {
        return value;
    }
};

export default async function PatientCompliancePage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    const logs = await fetchJson<ComplianceLogList>(
        `/patients/${id}/compliance?limit=30`
    );

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Compliance review</h2>
                    <Link className="text-link" href={`/patients/${id}`}>
                        Patient overview
                    </Link>
                </div>
                <p className="muted">
                    These logs are populated by mock engagement responses. Use
                    them to validate the feedback loop for the agentic workflow.
                </p>
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>Latest compliance logs</h2>
                    <span className="badge">Live</span>
                </div>
                {logs.data?.items?.length ? (
                    <div className="table">
                        <div className="table-head">
                            <span>Date</span>
                            <span>Fluids</span>
                            <span>Meds</span>
                            <span>Diet score</span>
                            <span></span>
                        </div>
                        {logs.data.items.map((log) => (
                            <div className="table-row" key={log.id}>
                                <span>{formatDate(log.log_date)}</span>
                                <span>
                                    {log.fluid_intake_ml
                                        ? `${log.fluid_intake_ml} ml`
                                        : "—"}
                                </span>
                                <span>
                                    {log.medication_taken === null ||
                                    log.medication_taken === undefined
                                        ? "—"
                                        : log.medication_taken
                                        ? "Yes"
                                        : "No"}
                                </span>
                                <span>
                                    {typeof log.dietary_compliance_score ===
                                    "number"
                                        ? `${Math.round(
                                              log.dietary_compliance_score * 100
                                          )}%`
                                        : "—"}
                                </span>
                                <span>{log.notes || ""}</span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="empty">
                        {logs.error
                            ? `Unable to load logs: ${logs.error}`
                            : "No compliance logs found yet."}
                    </p>
                )}
            </div>
        </section>
    );
}
