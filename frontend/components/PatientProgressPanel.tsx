"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import type { ComplianceLogList } from "@/lib/types";

const STORAGE_KEY = "kidneystone_last_patient_id";

const formatDate = (value: string) => {
    try {
        return new Date(value).toLocaleDateString();
    } catch (error) {
        return value;
    }
};

export default function PatientProgressPanel() {
    const [patientId, setPatientId] = useState("");
    const [logs, setLogs] = useState<ComplianceLogList | null>(null);
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [message, setMessage] = useState("");

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
            setPatientId(stored);
        }
    }, []);

    const loadProgress = async () => {
        if (!patientId.trim()) {
            setStatus("error");
            setMessage("Enter a patient ID to load progress.");
            return;
        }
        setStatus("loading");
        setMessage("");
        const response = await fetchJson<ComplianceLogList>(
            `/patients/${patientId}/compliance?limit=30`
        );
        if (response.error) {
            setStatus("error");
            setMessage(response.error);
            return;
        }
        setLogs(response.data || null);
        setStatus("idle");
        if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, patientId);
        }
    };

    const totalLogs = logs?.total || 0;
    const hydrationDays =
        logs?.items?.filter(
            (log) => log.fluid_intake_ml !== null && log.fluid_intake_ml !== undefined
        ).length || 0;
    const medDays =
        logs?.items?.filter(
            (log) => log.medication_taken !== null && log.medication_taken !== undefined
        ).length || 0;

    return (
        <div className="card">
            <div className="card-header">
                <h2>Progress from API</h2>
                <span className="badge">Live</span>
            </div>
            <div className="form-grid">
                <label>
                    Patient ID
                    <input
                        value={patientId}
                        onChange={(event) => setPatientId(event.target.value)}
                        placeholder="UUID"
                    />
                </label>
                <div className="actions">
                    <button
                        type="button"
                        onClick={loadProgress}
                        disabled={status === "loading"}
                    >
                        {status === "loading" ? "Loading..." : "Load progress"}
                    </button>
                    <p className={`status ${status}`}>
                        {message || "Ready."}
                    </p>
                </div>
            </div>

            {logs ? (
                <>
                    <div className="stat-grid">
                        <div className="stat-card">
                            <p className="eyebrow">Logs on file</p>
                            <h2>{totalLogs}</h2>
                            <p className="stat-note">Total daily check-ins.</p>
                        </div>
                        <div className="stat-card">
                            <p className="eyebrow">Hydration entries</p>
                            <h2>{hydrationDays}</h2>
                            <p className="stat-note">Days with fluid data.</p>
                        </div>
                        <div className="stat-card">
                            <p className="eyebrow">Medication tracking</p>
                            <h2>{medDays}</h2>
                            <p className="stat-note">Days with med status.</p>
                        </div>
                    </div>

                    {logs.items?.length ? (
                        <div className="table">
                            <div className="table-head">
                                <span>Date</span>
                                <span>Fluids</span>
                                <span>Meds</span>
                                <span>Diet score</span>
                                <span></span>
                            </div>
                            {logs.items.map((log) => (
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
                                                  log.dietary_compliance_score *
                                                      100
                                              )}%`
                                            : "—"}
                                    </span>
                                    <span>{log.notes || ""}</span>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="empty">No compliance logs yet.</p>
                    )}
                </>
            ) : (
                <p className="empty">No progress loaded yet.</p>
            )}
        </div>
    );
}
