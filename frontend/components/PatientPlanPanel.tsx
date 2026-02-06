"use client";

import { useEffect, useState } from "react";

import { fetchJson } from "@/lib/api";
import { formatMedgemmaSections } from "@/lib/medgemma";
import type { PreventionPlanOut } from "@/lib/types";

const STORAGE_KEY = "kidneystone_last_patient_id";

export default function PatientPlanPanel({
    patientId: patientIdProp,
    onPatientIdChange,
    showPatientInput = true,
    autoLoad = false,
    showSummary = true,
}: {
    patientId?: string;
    onPatientIdChange?: (value: string) => void;
    showPatientInput?: boolean;
    autoLoad?: boolean;
    showSummary?: boolean;
} = {}) {
    const isControlled = patientIdProp !== undefined;
    const [patientId, setPatientId] = useState(patientIdProp ?? "");
    const [plan, setPlan] = useState<PreventionPlanOut | null>(null);
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [message, setMessage] = useState("");

    useEffect(() => {
        if (isControlled) {
            setPatientId(patientIdProp || "");
        }
    }, [isControlled, patientIdProp]);

    useEffect(() => {
        if (isControlled || typeof window === "undefined") {
            return;
        }
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
            setPatientId(stored);
            onPatientIdChange?.(stored);
        }
    }, [isControlled, onPatientIdChange]);

    const loadPlan = async (options: { silentEmpty?: boolean } = {}) => {
        if (!patientId.trim()) {
            if (!options.silentEmpty) {
                setStatus("error");
                setMessage(
                    showPatientInput
                        ? "Enter a patient ID to load the plan."
                        : "Select a patient to load the plan."
                );
            }
            return;
        }
        setStatus("loading");
        setMessage("");
        const response = await fetchJson<PreventionPlanOut | null>(
            `/patients/${patientId}/plan`
        );
        if (response.error) {
            setStatus("error");
            setMessage(response.error);
            return;
        }
        setPlan(response.data || null);
        setStatus("idle");
        if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, patientId);
        }
        onPatientIdChange?.(patientId);
    };

    useEffect(() => {
        if (!autoLoad) {
            return;
        }
        if (!patientId.trim()) {
            setPlan(null);
            setStatus("idle");
            setMessage("");
            return;
        }
        loadPlan({ silentEmpty: true });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoLoad, patientId]);

    return (
        <div className="card">
            <div className="card-header">
                <h2>Plan from API</h2>
                <span className="badge">Live</span>
            </div>
            <div className="form-grid">
                {showPatientInput ? (
                    <label>
                        Patient ID
                        <input
                            value={patientId}
                            onChange={(event) => {
                                const value = event.target.value;
                                if (!isControlled) {
                                    setPatientId(value);
                                }
                                onPatientIdChange?.(value);
                            }}
                            placeholder="UUID"
                        />
                    </label>
                ) : null}
                <div className="actions">
                    <button
                        type="button"
                        onClick={() => {
                            loadPlan();
                        }}
                        disabled={status === "loading"}
                    >
                        {status === "loading"
                            ? "Loading..."
                            : showPatientInput
                            ? "Load plan"
                            : "Refresh plan"}
                    </button>
                    <p className={`status ${status}`}>
                        {message || "Ready."}
                    </p>
                </div>
            </div>

            {plan ? (
                <div className="preview">
                    <p>
                        <strong>Fluid target:</strong>{" "}
                        {plan.fluid_intake_target_ml
                            ? `${plan.fluid_intake_target_ml} ml/day`
                            : "N/A"}
                    </p>
                    <div className="preview-block">
                        <span>Dietary guidance</span>
                        <p>{plan.dietary_recommendations?.length || 0} categories</p>
                    </div>
                    <div className="preview-block">
                        <span>Medications</span>
                        <p>
                            {plan.medications_recommended?.length
                                ? plan.medications_recommended
                                      .map((med) => med.name)
                                      .filter(Boolean)
                                      .join(", ")
                                : "None"}
                        </p>
                    </div>
                    <div className="preview-block">
                        <span>Lifestyle</span>
                        <p>{plan.lifestyle_modifications?.length || 0} items</p>
                    </div>
                    {showSummary && plan.personalized_summary ? (
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
                </div>
            ) : (
                <p className="empty">No plan loaded yet.</p>
            )}
        </div>
    );
}
