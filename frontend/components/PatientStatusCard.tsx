import type { PatientOut } from "@/lib/types";

export default function PatientStatusCard({
    patient,
    adherence,
    lastCheckIn,
    statusLabel,
}: {
    patient: PatientOut;
    adherence?: number | null;
    lastCheckIn?: string | null;
    statusLabel?: string | null;
}) {
    return (
        <div className="card status-card">
            <div className="card-header">
                <div>
                    <p className="eyebrow">Patient</p>
                    <h3>
                        {patient.first_name} {patient.last_name}
                    </h3>
                </div>
                <span className="badge">{statusLabel || "Active"}</span>
            </div>
            <div className="info-list">
                <div>
                    <span>Adherence</span>
                    <strong>
                        {typeof adherence === "number"
                            ? `${Math.round(adherence * 100)}%`
                            : "—"}
                    </strong>
                </div>
                <div>
                    <span>Last check-in</span>
                    <strong>{lastCheckIn || "—"}</strong>
                </div>
                <div>
                    <span>Phone</span>
                    <strong>{patient.phone || "—"}</strong>
                </div>
                <div>
                    <span>SMS</span>
                    <strong>
                        {patient.contact_preferences?.sms ? "On" : "Off"}
                    </strong>
                </div>
            </div>
        </div>
    );
}
