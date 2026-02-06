"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import { formatMedgemmaSections } from "@/lib/medgemma";
import type { PreventionPlanOut, StoneAnalysisList, StoneAnalysisOut } from "@/lib/types";

// Live plan preview fetched from the API to avoid stale browser-local snapshots.

export default function LatestPlanPreview({
    patientId,
}: {
    patientId?: string;
}) {
    const [analysis, setAnalysis] = useState<StoneAnalysisOut | null>(null);
    const [plan, setPlan] = useState<PreventionPlanOut | null>(null);
    const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">(
        "idle"
    );
    const [message, setMessage] = useState("");

    useEffect(() => {
        if (!patientId) {
            setAnalysis(null);
            setPlan(null);
            setStatus("idle");
            setMessage("");
            return;
        }

        let isActive = true;
        const load = async () => {
            setStatus("loading");
            setMessage("");

            const [analysisResponse, planResponse] = await Promise.all([
                fetchJson<StoneAnalysisList>(
                    `/analyses/?patient_id=${patientId}&limit=1`
                ),
                fetchJson<PreventionPlanOut | null>(
                    `/patients/${patientId}/plan`
                ),
            ]);

            if (!isActive) {
                return;
            }

            if (analysisResponse.error) {
                setStatus("error");
                setMessage(analysisResponse.error);
                setAnalysis(null);
                setPlan(planResponse.data || null);
                return;
            }

            if (planResponse.error) {
                setStatus("error");
                setMessage(planResponse.error);
                setPlan(null);
                setAnalysis(analysisResponse.data?.items?.[0] || null);
                return;
            }

            setAnalysis(analysisResponse.data?.items?.[0] || null);
            setPlan(planResponse.data || null);
            setStatus("ready");
        };

        load();

        return () => {
            isActive = false;
        };
    }, [patientId]);

    if (!patientId) {
        return (
            <div className="card">
                <h2>Plan summary</h2>
                <p className="empty">
                    Select a patient to load the latest prevention plan.
                </p>
            </div>
        );
    }

    if (status === "error") {
        return (
            <div className="card">
                <h2>Plan summary</h2>
                <p className="status error">
                    {message || "Unable to load plan data."}
                </p>
            </div>
        );
    }

    if (status === "loading") {
        return (
            <div className="card">
                <h2>Plan summary</h2>
                <p className="status">Loading plan...</p>
            </div>
        );
    }

    if (!plan) {
        return (
            <div className="card">
                <h2>Plan summary</h2>
                <p className="empty">No prevention plan found yet.</p>
            </div>
        );
    }

    const medications = (plan.medications_recommended || [])
        .map((med) => {
            if (!med || typeof med !== "object") {
                return "";
            }
            const name = (med as { name?: unknown }).name;
            return typeof name === "string" ? name : "";
        })
        .filter(Boolean);
    const lifestyle = (plan.lifestyle_modifications || []).filter(
        (item) => typeof item === "string" && item.trim()
    );

    return (
        <div className="card">
            <div className="card-header">
                <h2>Plan summary</h2>
                <span className="badge">Live</span>
            </div>
            <div className="info-list">
                <div>
                    <span>Fluid target</span>
                    <strong>
                        {plan.fluid_intake_target_ml
                            ? `${plan.fluid_intake_target_ml} ml/day`
                            : "—"}
                    </strong>
                </div>
                <div>
                    <span>Treatment</span>
                    <strong>
                        {analysis?.treatment_recommendation || "—"}
                    </strong>
                </div>
                <div>
                    <span>Urgency</span>
                    <strong>{analysis?.urgency_level || "—"}</strong>
                </div>
                <div>
                    <span>Diet categories</span>
                    <strong>{plan.dietary_recommendations?.length || 0}</strong>
                </div>
            </div>
            <div className="pill">Live view of the latest approved plan.</div>
            <div className="preview">
                <div className="preview-block">
                    <span>Medications</span>
                    <p>
                        {medications.length
                            ? medications.join(", ")
                            : "None"}
                    </p>
                </div>
                <div className="preview-block">
                    <span>Lifestyle</span>
                    <p>
                        {lifestyle.length
                            ? lifestyle.join(", ")
                            : "None"}
                    </p>
                </div>
            </div>
            {plan.personalized_summary ? (
                <div className="quote-block summary-block">
                    {formatMedgemmaSections(
                        plan.personalized_summary
                    ).map((section, index) => (
                        <p
                            key={`${section.kind}-${index}`}
                            className={`summary-${section.kind}`}
                        >
                            {section.text}
                        </p>
                    ))}
                </div>
            ) : null}
            {plan.education_materials?.length ? (
                <div className="chip-row">
                    {plan.education_materials.map((item, index) => {
                        const title =
                            typeof item.title === "string" && item.title.trim()
                                ? item.title
                                : "Education";

                        return (
                            <span key={`${title}-${index}`} className="chip">
                                {title}
                            </span>
                        );
                    })}
                </div>
            ) : null}
        </div>
    );
}
