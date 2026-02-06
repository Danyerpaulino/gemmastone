"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import type { PreventionPlanOut, StoneAnalysisList, StoneAnalysisOut } from "@/lib/types";

// Fetches the latest analysis + plan from the API so clinicians can review and approve
// without relying on a browser-local snapshot.

export default function LatestRunPanel({
    patientId,
}: {
    patientId?: string;
}) {
    const [analysis, setAnalysis] = useState<StoneAnalysisOut | null>(null);
    const [plan, setPlan] = useState<PreventionPlanOut | null>(null);
    const [loadStatus, setLoadStatus] = useState<
        "idle" | "loading" | "ready" | "error"
    >("idle");
    const [loadMessage, setLoadMessage] = useState("");
    const [notes, setNotes] = useState("");
    const [modFluidTarget, setModFluidTarget] = useState("");
    const [modLifestyle, setModLifestyle] = useState("");
    const [modDietaryJson, setModDietaryJson] = useState("");
    const [modMedicationsJson, setModMedicationsJson] = useState("");
    const [modEducationJson, setModEducationJson] = useState("");
    const [modSummary, setModSummary] = useState("");
    const [status, setStatus] = useState<"idle" | "saving" | "done" | "error">(
        "idle"
    );
    const [message, setMessage] = useState("");

    useEffect(() => {
        if (!patientId) {
            setAnalysis(null);
            setPlan(null);
            setLoadStatus("idle");
            setLoadMessage("");
            return;
        }

        let isActive = true;
        const load = async () => {
            setLoadStatus("loading");
            setLoadMessage("");

            const [analysisResponse, planResponse] = await Promise.all([
                fetchJson<StoneAnalysisList>(
                    `/analyses/?patient_id=${patientId}&limit=1`
                ),
                fetchJson<PreventionPlanOut | null>(`/patients/${patientId}/plan`),
            ]);

            if (!isActive) {
                return;
            }

            if (analysisResponse.error) {
                setLoadStatus("error");
                setLoadMessage(analysisResponse.error);
                setAnalysis(null);
                setPlan(planResponse.data || null);
                return;
            }

            if (planResponse.error) {
                setLoadStatus("error");
                setLoadMessage(planResponse.error);
                setPlan(null);
                setAnalysis(analysisResponse.data?.items?.[0] || null);
                return;
            }

            setAnalysis(analysisResponse.data?.items?.[0] || null);
            setPlan(planResponse.data || null);
            setLoadStatus("ready");
        };

        load();

        return () => {
            isActive = false;
        };
    }, [patientId]);

    const buildModifications = () => {
        const modifications: Record<string, unknown> = {};

        if (modFluidTarget.trim()) {
            const value = Number(modFluidTarget);
            if (!Number.isFinite(value) || value <= 0) {
                throw new Error("Fluid target must be a positive number.");
            }
            modifications.fluid_intake_target_ml = Math.round(value);
        }

        if (modLifestyle.trim()) {
            const items = modLifestyle
                .split("\n")
                .map((line) => line.trim())
                .filter(Boolean);
            if (items.length) {
                modifications.lifestyle_modifications = items;
            }
        }

        if (modDietaryJson.trim()) {
            const parsed = JSON.parse(modDietaryJson);
            if (!Array.isArray(parsed)) {
                throw new Error(
                    "Dietary recommendations must be a JSON array of objects."
                );
            }
            modifications.dietary_recommendations = parsed;
        }

        if (modMedicationsJson.trim()) {
            const parsed = JSON.parse(modMedicationsJson);
            if (!Array.isArray(parsed)) {
                throw new Error(
                    "Medications must be a JSON array of objects."
                );
            }
            modifications.medications_recommended = parsed;
        }

        if (modEducationJson.trim()) {
            const parsed = JSON.parse(modEducationJson);
            if (!Array.isArray(parsed)) {
                throw new Error(
                    "Education materials must be a JSON array of objects."
                );
            }
            modifications.education_materials = parsed;
        }

        if (modSummary.trim()) {
            modifications.personalized_summary = modSummary.trim();
        }

        return Object.keys(modifications).length ? modifications : null;
    };

    const approvePlan = async () => {
        if (!plan?.id) {
            setStatus("error");
            setMessage("No plan ID found. Run a CT intake first.");
            return;
        }
        setStatus("saving");
        setMessage("");

        let modifications: Record<string, unknown> | null = null;
        try {
            modifications = buildModifications();
        } catch (error) {
            setStatus("error");
            setMessage(
                error instanceof Error ? error.message : "Invalid modifications."
            );
            return;
        }

        const body: Record<string, unknown> = {
            provider_notes: notes || null,
        };
        if (modifications) {
            body.modifications = modifications;
        }

        const response = await fetchJson<PreventionPlanOut>(
            `/plans/${plan.id}/approve`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
            }
        );

        if (response.error) {
            setStatus("error");
            setMessage(response.error);
            return;
        }

        if (response.data) {
            setPlan(response.data);
        }
        setStatus("done");
        setMessage("Plan approved. Pending nudges are now scheduled.");
    };

    if (!patientId) {
        return (
            <div className="card">
                <h2>Latest run</h2>
                <p className="empty">
                    Provide a patient ID to load their latest analysis and plan.
                </p>
            </div>
        );
    }

    if (loadStatus === "error") {
        return (
            <div className="card">
                <h2>Latest run</h2>
                <p className="status error">{loadMessage || "Unable to load data."}</p>
            </div>
        );
    }

    return (
        <div className="card">
            <div className="card-header">
                <h2>Latest run</h2>
                <span className="badge">Live</span>
            </div>
            {loadStatus === "loading" ? (
                <p className="status">Loading latest analysis...</p>
            ) : analysis || plan ? (
                <div className="info-list">
                    <div>
                        <span>Composition</span>
                        <strong>{analysis?.predicted_composition || "Unknown"}</strong>
                    </div>
                    <div>
                        <span>Treatment</span>
                        <strong>{analysis?.treatment_recommendation || "Pending"}</strong>
                    </div>
                    <div>
                        <span>Urgency</span>
                        <strong>{analysis?.urgency_level || "Routine"}</strong>
                    </div>
                    <div>
                        <span>Fluid target</span>
                        <strong>
                            {plan?.fluid_intake_target_ml
                                ? `${plan.fluid_intake_target_ml} ml/day`
                                : "—"}
                        </strong>
                    </div>
                </div>
            ) : (
                <p className="empty">No analysis or plan found yet.</p>
            )}

            <div className="form-grid single">
                <label>
                    Provider notes (optional)
                    <textarea
                        rows={3}
                        value={notes}
                        onChange={(event) => setNotes(event.target.value)}
                        placeholder="Add any clinical context or adjustments."
                    />
                </label>
            </div>

            <h3>Plan adjustments (optional)</h3>
            <p className="muted">
                Only fill the fields you want to override. Submitting changes
                creates a new plan version.
            </p>
            <div className="form-grid">
                <label>
                    Fluid target (ml/day)
                    <input
                        value={modFluidTarget}
                        onChange={(event) =>
                            setModFluidTarget(event.target.value)
                        }
                        placeholder="3000"
                    />
                </label>
                <label>
                    Personalized summary
                    <input
                        value={modSummary}
                        onChange={(event) => setModSummary(event.target.value)}
                        placeholder="Short patient-friendly summary"
                    />
                </label>
            </div>
            <div className="form-grid single">
                <label>
                    Lifestyle modifications (one per line)
                    <textarea
                        rows={4}
                        value={modLifestyle}
                        onChange={(event) =>
                            setModLifestyle(event.target.value)
                        }
                        placeholder="Drink 3L water daily&#10;Limit sodium to 2,300mg"
                    />
                </label>
            </div>
            <div className="form-grid single">
                <label>
                    Dietary recommendations (JSON array)
                    <textarea
                        rows={4}
                        value={modDietaryJson}
                        onChange={(event) =>
                            setModDietaryJson(event.target.value)
                        }
                        placeholder='[{"category":"reduce","items":[{"item":"spinach","reason":"High oxalate"}],"priority":"high"}]'
                    />
                </label>
            </div>
            <div className="form-grid single">
                <label>
                    Medications (JSON array)
                    <textarea
                        rows={3}
                        value={modMedicationsJson}
                        onChange={(event) =>
                            setModMedicationsJson(event.target.value)
                        }
                        placeholder='[{"name":"potassium citrate","dose":"20 mEq twice daily"}]'
                    />
                </label>
            </div>
            <div className="form-grid single">
                <label>
                    Education materials (JSON array)
                    <textarea
                        rows={3}
                        value={modEducationJson}
                        onChange={(event) =>
                            setModEducationJson(event.target.value)
                        }
                        placeholder='[{"type":"pdf","title":"Hydration Guide","url":"/materials/hydration-guide.pdf"}]'
                    />
                </label>
            </div>

            <div className="actions">
                <button
                    type="button"
                    disabled={status === "saving" || !plan?.id}
                    onClick={approvePlan}
                >
                    {status === "saving" ? "Approving..." : "Approve plan"}
                </button>
                <p className={`status ${status}`}>
                    {message || "Ready to approve."}
                </p>
            </div>
        </div>
    );
}
