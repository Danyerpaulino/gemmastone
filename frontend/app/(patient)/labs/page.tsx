"use client";

import { useEffect, useMemo, useState } from "react";

import LabTrendChart from "@/components/LabTrendChart";
import { fetchJson } from "@/lib/api";
import { useAuthSession } from "@/lib/auth";
import type { LabResultList, LabResultOut } from "@/lib/types";

const formatDate = (value?: string | null) => {
    if (!value) {
        return "—";
    }
    try {
        return new Date(value).toLocaleDateString();
    } catch (error) {
        return value;
    }
};

const summarizeResult = (lab: LabResultOut) => {
    if (!lab.results) {
        return "—";
    }
    const keys = Object.keys(lab.results).slice(0, 3);
    return keys
        .map((key) => `${key}: ${String(lab.results[key])}`)
        .join(" · ");
};

export default function PatientLabsPage() {
    const { session } = useAuthSession({ required: true });
    const [labs, setLabs] = useState<LabResultOut[]>([]);
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
            const response = await fetchJson<LabResultList>(
                `/labs?patient_id=${session.patientId}&limit=50`
            );
            if (!active) {
                return;
            }
            if (response.error) {
                setStatus("error");
                setMessage(response.error);
                return;
            }
            setLabs(response.data?.items || []);
            setStatus("idle");
        };
        load();
        return () => {
            active = false;
        };
    }, [session?.patientId]);

    const labsAvailable = useMemo(() => labs.length > 0, [labs]);

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Lab trends</h2>
                    <span className="badge">Live</span>
                </div>
                <p className="muted">
                    We track lab changes over time to keep your plan personalized.
                    Uploads from your care team sync automatically.
                </p>
            </div>

            {status === "error" ? (
                <div className="card">
                    <p className="status error">{message}</p>
                </div>
            ) : null}

            <div className="grid">
                <LabTrendChart
                    labs={labs}
                    metricKey="volume_ml_day"
                    label="24h urine volume"
                    unit="ml"
                />
                <LabTrendChart
                    labs={labs}
                    metricKey="citrate_mg_day"
                    label="Citrate"
                    unit="mg/day"
                />
                <LabTrendChart
                    labs={labs}
                    metricKey="sodium_mg_day"
                    label="Sodium"
                    unit="mg/day"
                />
            </div>

            <div className="card">
                <div className="card-header">
                    <h2>Recent lab results</h2>
                </div>
                {labsAvailable ? (
                    <div className="table">
                        <div className="table-head">
                            <span>Date</span>
                            <span>Type</span>
                            <span>Summary</span>
                            <span></span>
                        </div>
                        {labs.map((lab) => (
                            <div className="table-row" key={lab.id}>
                                <span>{formatDate(lab.result_date || lab.created_at)}</span>
                                <span>{lab.result_type}</span>
                                <span>{summarizeResult(lab)}</span>
                                <span className="muted">Synced</span>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="empty">
                        {status === "loading" ? "Loading labs..." : "No labs yet."}
                    </p>
                )}
            </div>
        </section>
    );
}
