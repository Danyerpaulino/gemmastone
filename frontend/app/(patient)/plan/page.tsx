"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchJson } from "@/lib/api";
import { useAuthSession } from "@/lib/auth";
import { formatMedgemmaSections } from "@/lib/medgemma";
import type { PreventionPlanOut } from "@/lib/types";

export default function PatientPlanPage() {
    const { session } = useAuthSession({ required: true });
    const [plan, setPlan] = useState<PreventionPlanOut | null>(null);
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
            const response = await fetchJson<PreventionPlanOut | null>(
                `/patients/${session.patientId}/plan`
            );
            if (!active) {
                return;
            }
            if (response.error) {
                setStatus("error");
                setMessage(response.error);
                return;
            }
            setPlan(response.data || null);
            setStatus("idle");
        };
        load();
        return () => {
            active = false;
        };
    }, [session?.patientId]);

    const medications = useMemo(() => {
        if (!plan?.medications_recommended) {
            return [];
        }
        return plan.medications_recommended
            .map((item) =>
                typeof item?.name === "string" ? item.name : undefined
            )
            .filter(Boolean) as string[];
    }, [plan]);

    if (status === "error") {
        return (
            <section className="stack">
                <div className="card">
                    <h2>Plan unavailable</h2>
                    <p className="status error">{message}</p>
                </div>
            </section>
        );
    }

    if (status === "loading") {
        return (
            <section className="stack">
                <div className="card">
                    <p className="status">Loading your plan...</p>
                </div>
            </section>
        );
    }

    if (!plan) {
        return (
            <section className="stack">
                <div className="card">
                    <h2>Your plan is in progress</h2>
                    <p className="muted">
                        We are building your personalized prevention plan. You'll
                        receive a text when it's ready.
                    </p>
                </div>
            </section>
        );
    }

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Prevention plan</h2>
                    <span className="badge">Active</span>
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
                        <span>Diet focus areas</span>
                        <strong>{plan.dietary_recommendations?.length || 0}</strong>
                    </div>
                    <div>
                        <span>Medications</span>
                        <strong>{medications.length || 0}</strong>
                    </div>
                    <div>
                        <span>Lifestyle habits</span>
                        <strong>{plan.lifestyle_modifications?.length || 0}</strong>
                    </div>
                </div>
            </div>

            {plan.personalized_summary ? (
                <div className="card">
                    <h2>Summary</h2>
                    <div className="quote-block summary-block">
                        {formatMedgemmaSections(plan.personalized_summary).map(
                            (section, index) => (
                                <p
                                    key={`${section.kind}-${index}`}
                                    className={`summary-${section.kind}`}
                                >
                                    {section.text}
                                </p>
                            )
                        )}
                    </div>
                </div>
            ) : null}

            <div className="grid">
                <div className="card">
                    <h2>Dietary guidance</h2>
                    <div className="chip-row">
                        {(plan.dietary_recommendations || []).map((item, index) => (
                            <span key={`${item?.category || "diet"}-${index}`} className="chip">
                                {item?.category || "Diet"}
                            </span>
                        ))}
                    </div>
                    <p className="muted">
                        We'll send meal-specific tips over SMS based on these focus
                        areas.
                    </p>
                </div>
                <div className="card">
                    <h2>Medications</h2>
                    {medications.length ? (
                        <ul className="list">
                            {medications.map((med) => (
                                <li key={med}>{med}</li>
                            ))}
                        </ul>
                    ) : (
                        <p className="muted">No medications listed.</p>
                    )}
                </div>
                <div className="card">
                    <h2>Lifestyle</h2>
                    {plan.lifestyle_modifications?.length ? (
                        <ul className="list">
                            {plan.lifestyle_modifications.map((item) => (
                                <li key={item}>{item}</li>
                            ))}
                        </ul>
                    ) : (
                        <p className="muted">No lifestyle updates yet.</p>
                    )}
                </div>
            </div>
        </section>
    );
}
