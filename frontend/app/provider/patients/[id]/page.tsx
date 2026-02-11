"use client";

import Link from "next/link";
import { use, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import AdherenceChart from "@/components/AdherenceChart";
import CallTranscript from "@/components/CallTranscript";
import LabTrendChart from "@/components/LabTrendChart";
import LatestPlanPreview from "@/components/LatestPlanPreview";
import LatestRunPanel from "@/components/LatestRunPanel";
import LabUploadPanel from "@/components/LabUploadPanel";
import SMSThread from "@/components/SMSThread";
import { fetchJson } from "@/lib/api";
import type {
    ComplianceLogList,
    LabResultList,
    PatientOut,
    SmsMessageList,
    VoiceCallList,
} from "@/lib/types";

const tabs = [
    { id: "overview", label: "Overview" },
    { id: "calls", label: "Calls" },
    { id: "messages", label: "Messages" },
    { id: "labs", label: "Labs" },
    { id: "plan", label: "Plan" },
] as const;

type TabId = (typeof tabs)[number]["id"];

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

export default function ProviderPatientDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const router = useRouter();
    const searchParams = useSearchParams();
    const initialTab = (searchParams.get("tab") || "overview") as TabId;
    const [tab, setTab] = useState<TabId>(
        tabs.some((item) => item.id === initialTab) ? initialTab : "overview"
    );

    const [patient, setPatient] = useState<PatientOut | null>(null);
    const [logs, setLogs] = useState<ComplianceLogList | null>(null);
    const [labs, setLabs] = useState<LabResultList | null>(null);
    const [calls, setCalls] = useState<VoiceCallList | null>(null);
    const [messages, setMessages] = useState<SmsMessageList | null>(null);
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [message, setMessage] = useState("");
    const [callStatus, setCallStatus] = useState("");

    useEffect(() => {
        const current = searchParams.get("tab") as TabId | null;
        if (current && tabs.some((item) => item.id === current)) {
            setTab(current);
        }
    }, [searchParams]);

    useEffect(() => {
        let active = true;
        const load = async () => {
            setStatus("loading");
            setMessage("");
            const [patientRes, logsRes, labsRes, callsRes, messagesRes] =
                await Promise.all([
                    fetchJson<PatientOut>(`/patients/${id}`),
                    fetchJson<ComplianceLogList>(
                        `/patients/${id}/compliance?limit=30`
                    ),
                    fetchJson<LabResultList>(`/labs?patient_id=${id}&limit=50`),
                    fetchJson<VoiceCallList>(`/voice/calls/${id}`),
                    fetchJson<SmsMessageList>(`/patients/${id}/sms?limit=50`),
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
            setLogs(logsRes.data || null);
            setLabs(labsRes.data || null);
            setCalls(callsRes.data || null);
            setMessages(messagesRes.data || null);
            setStatus("idle");
        };
        load();
        return () => {
            active = false;
        };
    }, [id]);

    const handleTabChange = (next: TabId) => {
        setTab(next);
        router.replace(`/provider/patients/${id}?tab=${next}`);
    };

    const triggerCall = async (callType: string) => {
        setCallStatus("Scheduling call...");
        const response = await fetchJson(`/voice/call/${id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ call_type: callType }),
        });
        if (response.error) {
            setCallStatus(response.error);
            return;
        }
        setCallStatus("Call queued.");
    };

    const adherenceScore = useMemo(() => {
        if (!logs?.items?.length) {
            return null;
        }
        const score = logs.items.reduce((acc, log) => {
            const hydration = log.fluid_intake_ml && log.fluid_intake_ml > 0 ? 1 : 0;
            const meds = log.medication_taken ? 1 : 0;
            const diet =
                typeof log.dietary_compliance_score === "number"
                    ? Math.max(0, Math.min(1, log.dietary_compliance_score))
                    : 0;
            return acc + (hydration + meds + diet) / 3;
        }, 0);
        return score / logs.items.length;
    }, [logs]);

    if (status === "error") {
        return (
            <section className="stack">
                <div className="card">
                    <h2>Unable to load patient</h2>
                    <p className="status error">{message}</p>
                </div>
            </section>
        );
    }

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <div>
                        <p className="eyebrow">Patient profile</p>
                        <h2>
                            {patient
                                ? `${patient.first_name} ${patient.last_name}`
                                : "Loading..."}
                        </h2>
                    </div>
                    <Link className="text-link" href="/provider/patients">
                        Back to list
                    </Link>
                </div>
                <div className="info-list">
                    <div>
                        <span>Phone</span>
                        <strong>{patient?.phone || "—"}</strong>
                    </div>
                    <div>
                        <span>Email</span>
                        <strong>{patient?.email || "—"}</strong>
                    </div>
                    <div>
                        <span>Adherence</span>
                        <strong>
                            {typeof adherenceScore === "number"
                                ? `${Math.round(adherenceScore * 100)}%`
                                : "—"}
                        </strong>
                    </div>
                    <div>
                        <span>Last check-in</span>
                        <strong>{formatDate(logs?.items?.[0]?.log_date)}</strong>
                    </div>
                </div>
            </div>

            <div className="tab-row">
                {tabs.map((item) => (
                    <button
                        key={item.id}
                        type="button"
                        className={`tab ${tab === item.id ? "active" : ""}`}
                        onClick={() => handleTabChange(item.id)}
                    >
                        {item.label}
                    </button>
                ))}
            </div>

            {tab === "overview" ? (
                <div className="stack">
                    {logs?.items ? <AdherenceChart logs={logs.items} /> : null}
                    <div className="grid">
                        <div className="card">
                            <h2>Engagement status</h2>
                            <p className="muted">
                                {patient?.communication_paused
                                    ? "Patient has paused communications."
                                    : "Communications are active."}
                            </p>
                            <div className="info-list">
                                <div>
                                    <span>SMS</span>
                                    <strong>
                                        {patient?.contact_preferences?.sms ? "On" : "Off"}
                                    </strong>
                                </div>
                                <div>
                                    <span>Voice</span>
                                    <strong>
                                        {patient?.contact_preferences?.voice ? "On" : "Off"}
                                    </strong>
                                </div>
                                <div>
                                    <span>Context version</span>
                                    <strong>{patient?.context_version ?? "—"}</strong>
                                </div>
                                <div>
                                    <span>Last context build</span>
                                    <strong>{formatDate(patient?.last_context_build)}</strong>
                                </div>
                            </div>
                        </div>
                        <div className="card">
                            <h2>Next actions</h2>
                            <ul className="list">
                                <li>Review adherence summary</li>
                                <li>Schedule follow-up call if needed</li>
                                <li>Send lab reminders</li>
                            </ul>
                        </div>
                    </div>
                </div>
            ) : null}

            {tab === "calls" ? (
                <div className="stack">
                    <div className="card">
                        <div className="card-header">
                            <h2>Call actions</h2>
                        </div>
                        <div className="actions">
                            <button type="button" onClick={() => triggerCall("follow_up")}>
                                Schedule follow-up
                            </button>
                            <button type="button" className="ghost" onClick={() => triggerCall("callback")}>
                                Schedule callback
                            </button>
                            <p className="status">{callStatus}</p>
                        </div>
                    </div>
                    <CallTranscript calls={calls?.items || []} />
                </div>
            ) : null}

            {tab === "messages" ? (
                <div className="stack">
                    <div className="card">
                        <div className="card-header">
                            <h2>SMS thread</h2>
                            <span className="badge">Live</span>
                        </div>
                        <p className="muted">
                            All inbound and outbound messages are logged here for
                            compliance review.
                        </p>
                    </div>
                    <SMSThread messages={messages?.items || []} />
                </div>
            ) : null}

            {tab === "labs" ? (
                <div className="stack">
                    <div className="grid">
                        <LabTrendChart
                            labs={labs?.items || []}
                            metricKey="volume_ml_day"
                            label="24h urine volume"
                            unit="ml"
                        />
                        <LabTrendChart
                            labs={labs?.items || []}
                            metricKey="citrate_mg_day"
                            label="Citrate"
                            unit="mg/day"
                        />
                        <LabTrendChart
                            labs={labs?.items || []}
                            metricKey="sodium_mg_day"
                            label="Sodium"
                            unit="mg/day"
                        />
                    </div>
                    <LabUploadPanel patientId={id} />
                </div>
            ) : null}

            {tab === "plan" ? (
                <div className="grid">
                    <LatestPlanPreview patientId={id} />
                    <LatestRunPanel patientId={id} />
                </div>
            ) : null}
        </section>
    );
}
