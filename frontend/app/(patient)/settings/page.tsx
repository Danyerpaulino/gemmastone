"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import { useAuthSession } from "@/lib/auth";
import type { PatientOut } from "@/lib/types";

const formatTime = (value?: string | null) => {
    if (!value) {
        return "—";
    }
    return value;
};

export default function PatientSettingsPage() {
    const { session } = useAuthSession({ required: true });
    const [patient, setPatient] = useState<PatientOut | null>(null);
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [message, setMessage] = useState("");

    useEffect(() => {
        if (!session?.patientId) {
            return;
        }
        let active = true;
        const load = async () => {
            setStatus("loading");
            setMessage("");
            const response = await fetchJson<PatientOut>(
                `/patients/${session.patientId}`
            );
            if (!active) {
                return;
            }
            if (response.error) {
                setStatus("error");
                setMessage(response.error);
                return;
            }
            setPatient(response.data || null);
            setStatus("idle");
        };
        load();
        return () => {
            active = false;
        };
    }, [session?.patientId]);

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Profile & preferences</h2>
                    <span className="badge">Secure</span>
                </div>
                <p className="muted">
                    Update your contact preferences with your care team. We
                    always honor quiet hours and opt-out requests.
                </p>
            </div>

            {status === "error" ? (
                <div className="card">
                    <p className="status error">{message}</p>
                </div>
            ) : null}

            <div className="grid">
                <div className="card">
                    <h2>Contact details</h2>
                    <div className="info-list">
                        <div>
                            <span>Name</span>
                            <strong>
                                {patient
                                    ? `${patient.first_name} ${patient.last_name}`
                                    : "—"}
                            </strong>
                        </div>
                        <div>
                            <span>Phone</span>
                            <strong>{patient?.phone || "—"}</strong>
                        </div>
                        <div>
                            <span>Email</span>
                            <strong>{patient?.email || "—"}</strong>
                        </div>
                        <div>
                            <span>Provider ID</span>
                            <strong>{patient?.provider_id || "—"}</strong>
                        </div>
                    </div>
                </div>
                <div className="card">
                    <h2>Notification channels</h2>
                    <div className="toggle-list">
                        <div>
                            <span>SMS reminders</span>
                            <strong>
                                {patient?.contact_preferences?.sms ? "On" : "Off"}
                            </strong>
                        </div>
                        <div>
                            <span>Voice check-ins</span>
                            <strong>
                                {patient?.contact_preferences?.voice ? "On" : "Off"}
                            </strong>
                        </div>
                        <div>
                            <span>Email summaries</span>
                            <strong>
                                {patient?.contact_preferences?.email ? "On" : "Off"}
                            </strong>
                        </div>
                    </div>
                    <p className="muted">
                        Changes are managed by your care team during onboarding.
                    </p>
                </div>
                <div className="card">
                    <h2>Quiet hours</h2>
                    <div className="info-list">
                        <div>
                            <span>Start</span>
                            <strong>{formatTime(patient?.quiet_hours_start)}</strong>
                        </div>
                        <div>
                            <span>End</span>
                            <strong>{formatTime(patient?.quiet_hours_end)}</strong>
                        </div>
                        <div>
                            <span>Comms paused</span>
                            <strong>{patient?.communication_paused ? "Yes" : "No"}</strong>
                        </div>
                        <div>
                            <span>Phone verified</span>
                            <strong>{patient?.phone_verified ? "Yes" : "No"}</strong>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
