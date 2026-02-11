"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import AdherenceChart from "@/components/AdherenceChart";
import { fetchJson } from "@/lib/api";
import { useAuthSession } from "@/lib/auth";
import type {
    ComplianceLogList,
    PatientOut,
    PreventionPlanOut,
    VoiceCallList,
} from "@/lib/types";

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

const buildHydrationStreak = (logs: ComplianceLogList | null) => {
    if (!logs?.items?.length) {
        return 0;
    }
    let streak = 0;
    for (const log of logs.items) {
        if (log.fluid_intake_ml && log.fluid_intake_ml > 0) {
            streak += 1;
        } else {
            break;
        }
    }
    return streak;
};

export default function PatientDashboardPage() {
    const { session } = useAuthSession({ required: true });
    const [patient, setPatient] = useState<PatientOut | null>(null);
    const [plan, setPlan] = useState<PreventionPlanOut | null>(null);
    const [logs, setLogs] = useState<ComplianceLogList | null>(null);
    const [calls, setCalls] = useState<VoiceCallList | null>(null);
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
            const [patientRes, planRes, logsRes, callsRes] = await Promise.all([
                fetchJson<PatientOut>(`/patients/${session.patientId}`),
                fetchJson<PreventionPlanOut | null>(
                    `/patients/${session.patientId}/plan`
                ),
                fetchJson<ComplianceLogList>(
                    `/patients/${session.patientId}/compliance?limit=30`
                ),
                fetchJson<VoiceCallList>(`/voice/calls/${session.patientId}`),
            ]);

            if (!active) {
                return;
            }
            if (patientRes.error) {
                setStatus("error");
                setMessage(patientRes.error);
                return;
            }
            setPatient(patientRes.data || null);
            setPlan(planRes.data || null);
            setLogs(logsRes.data || null);
            setCalls(callsRes.data || null);
            setStatus("idle");
        };
        load();
        return () => {
            active = false;
        };
    }, [session?.patientId]);

    const hydrationTarget = plan?.fluid_intake_target_ml;
    const lastCall = calls?.items?.[0];
    const lastCheckIn = logs?.items?.[0];

    const hydrationStreak = useMemo(() => buildHydrationStreak(logs), [logs]);

    if (status === "error") {
        return (
            <section className="stack">
                <div className="card">
                    <h2>Unable to load your dashboard</h2>
                    <p className="status error">{message}</p>
                </div>
            </section>
        );
    }

    return (
        <section className="stack">
            <div className="card hero-card">
                <div>
                    <p className="eyebrow">Your prevention assistant</p>
                    <h1>
                        Welcome back{patient?.first_name ? `, ${patient.first_name}` : ""}.
                    </h1>
                    <p className="lead">
                        Your next check-in is always just a text away. We keep
                        your plan updated and your care team in the loop.
                    </p>
                </div>
                <div className="hero-metrics">
                    <div>
                        <span>Hydration goal</span>
                        <strong>
                            {hydrationTarget ? `${hydrationTarget} ml/day` : "—"}
                        </strong>
                    </div>
                    <div>
                        <span>Streak</span>
                        <strong>{hydrationStreak} days</strong>
                    </div>
                    <div>
                        <span>Last check-in</span>
                        <strong>{formatDate(lastCheckIn?.log_date)}</strong>
                    </div>
                </div>
            </div>

            <div className="stat-grid">
                <div className="stat-card">
                    <p className="eyebrow">Recent call</p>
                    <h3>{lastCall ? lastCall.call_type : "No calls yet"}</h3>
                    <p className="muted">
                        {lastCall?.started_at
                            ? `Last call on ${formatDate(lastCall.started_at)}`
                            : "We will call after your intake."}
                    </p>
                </div>
                <div className="stat-card">
                    <p className="eyebrow">SMS status</p>
                    <h3>
                        {patient?.contact_preferences?.sms ? "Enabled" : "Paused"}
                    </h3>
                    <p className="muted">
                        {patient?.communication_paused
                            ? "Reply START to resume reminders."
                            : "Reply STOP at any time to pause."}
                    </p>
                </div>
                <div className="stat-card">
                    <p className="eyebrow">Plan snapshot</p>
                    <h3>{plan ? "Active" : "Pending"}</h3>
                    <p className="muted">
                        {plan?.personalized_summary
                            ? "Plan updated from your latest records."
                            : "We are building your plan."}
                    </p>
                </div>
            </div>

            {logs?.items ? <AdherenceChart logs={logs.items} /> : null}

            <div className="grid">
                <div className="card">
                    <div className="card-header">
                        <h2>Your plan</h2>
                        <Link className="text-link" href="/plan">
                            View details
                        </Link>
                    </div>
                    <p className="muted">
                        Hydration, diet, and medication targets personalized to
                        your latest lab and imaging data.
                    </p>
                    <div className="info-list">
                        <div>
                            <span>Fluid target</span>
                            <strong>
                                {hydrationTarget
                                    ? `${hydrationTarget} ml/day`
                                    : "—"}
                            </strong>
                        </div>
                        <div>
                            <span>Dietary focus</span>
                            <strong>
                                {plan?.dietary_recommendations?.length || 0} areas
                            </strong>
                        </div>
                        <div>
                            <span>Medications</span>
                            <strong>
                                {plan?.medications_recommended?.length || 0}
                            </strong>
                        </div>
                        <div>
                            <span>Next step</span>
                            <strong>Reply to weekly check-ins</strong>
                        </div>
                    </div>
                </div>
                <div className="card">
                    <div className="card-header">
                        <h2>Need support?</h2>
                    </div>
                    <p className="muted">
                        Text your questions anytime. We respond with guidance
                        based on your urologist-approved plan.
                    </p>
                    <div className="actions">
                        <Link className="ghost-link" href="/settings">
                            Update preferences
                        </Link>
                        <Link className="ghost-link" href="/labs">
                            Review labs
                        </Link>
                    </div>
                </div>
            </div>
        </section>
    );
}
