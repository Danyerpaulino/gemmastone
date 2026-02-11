import Link from "next/link";

import PatientStatusCard from "@/components/PatientStatusCard";
import { fetchJson } from "@/lib/api";
import type { ComplianceLogList, PatientList } from "@/lib/types";

const formatDate = (value?: string | null) => {
    if (!value) {
        return "—";
    }
    try {
        return new Date(value).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
        });
    } catch (error) {
        return value;
    }
};

const computeAdherence = (logs: ComplianceLogList | null) => {
    const items = logs?.items || [];
    if (!items.length) {
        return null;
    }
    const score = items.reduce((acc, log) => {
        const hydration = log.fluid_intake_ml && log.fluid_intake_ml > 0 ? 1 : 0;
        const meds = log.medication_taken ? 1 : 0;
        const diet =
            typeof log.dietary_compliance_score === "number"
                ? Math.max(0, Math.min(1, log.dietary_compliance_score))
                : 0;
        return acc + (hydration + meds + diet) / 3;
    }, 0);
    return score / items.length;
};

export default async function ProviderDashboard() {
    const patients = await fetchJson<PatientList>("/patients/?limit=12");
    const patientItems = patients.data?.items || [];

    const complianceSnapshots = await Promise.all(
        patientItems.map(async (patient) => {
            const logs = await fetchJson<ComplianceLogList>(
                `/patients/${patient.id}/compliance?limit=7`
            );
            return {
                patient,
                logs: logs.data || null,
                adherence: computeAdherence(logs.data || null),
                lastCheckIn: logs.data?.items?.[0]?.log_date || null,
            };
        })
    );

    const totalPatients = patientItems.length;
    const pausedCount = patientItems.filter((patient) => patient.communication_paused)
        .length;
    const smsEnabled = patientItems.filter(
        (patient) => patient.contact_preferences?.sms
    ).length;

    return (
        <section className="stack">
            <div className="card hero-card">
                <div>
                    <p className="eyebrow">Compliance command center</p>
                    <h1>Stone prevention engagement</h1>
                    <p className="lead">
                        Track adherence across calls and SMS. Prioritize outreach
                        for patients who need coaching.
                    </p>
                </div>
                <div className="hero-metrics">
                    <div>
                        <span>Active patients</span>
                        <strong>{totalPatients || "—"}</strong>
                    </div>
                    <div>
                        <span>SMS enabled</span>
                        <strong>{smsEnabled || 0}</strong>
                    </div>
                    <div>
                        <span>Paused</span>
                        <strong>{pausedCount || 0}</strong>
                    </div>
                </div>
            </div>

            <div className="stat-grid">
                {complianceSnapshots.slice(0, 3).map((snapshot) => (
                    <PatientStatusCard
                        key={snapshot.patient.id}
                        patient={snapshot.patient}
                        adherence={snapshot.adherence}
                        lastCheckIn={formatDate(snapshot.lastCheckIn)}
                        statusLabel={snapshot.patient.communication_paused ? "Paused" : "Active"}
                    />
                ))}
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>Patient compliance snapshot</h2>
                    <Link className="text-link" href="/provider/patients">
                        View all patients
                    </Link>
                </div>
                {complianceSnapshots.length ? (
                    <div className="table">
                        <div className="table-head">
                            <span>Patient</span>
                            <span>Last check-in</span>
                            <span>Adherence</span>
                            <span>SMS</span>
                            <span>Status</span>
                        </div>
                        {complianceSnapshots.map((snapshot) => (
                            <div className="table-row" key={snapshot.patient.id}>
                                <span>
                                    {snapshot.patient.first_name} {snapshot.patient.last_name}
                                </span>
                                <span>{formatDate(snapshot.lastCheckIn)}</span>
                                <span>
                                    {typeof snapshot.adherence === "number"
                                        ? `${Math.round(snapshot.adherence * 100)}%`
                                        : "—"}
                                </span>
                                <span>
                                    {snapshot.patient.contact_preferences?.sms ? "On" : "Off"}
                                </span>
                                <Link
                                    className="text-link"
                                    href={`/provider/patients/${snapshot.patient.id}`}
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
