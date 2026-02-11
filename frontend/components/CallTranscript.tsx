"use client";

import type { VoiceCallOut } from "@/lib/types";

const formatDateTime = (value?: string | null) => {
    if (!value) {
        return "—";
    }
    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
};

const formatDuration = (seconds?: number | null) => {
    if (!seconds) {
        return "—";
    }
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
};

export default function CallTranscript({ calls }: { calls: VoiceCallOut[] }) {
    if (!calls.length) {
        return <p className="empty">No call history yet.</p>;
    }

    return (
        <div className="stack">
            {calls.map((call) => (
                <div key={call.id} className="card transcript-card">
                    <div className="card-header">
                        <div>
                            <p className="eyebrow">{call.call_type}</p>
                            <h3>{formatDateTime(call.started_at)}</h3>
                        </div>
                        <div className="pill">{call.status}</div>
                    </div>
                    <div className="info-list">
                        <div>
                            <span>Direction</span>
                            <strong>{call.direction}</strong>
                        </div>
                        <div>
                            <span>Duration</span>
                            <strong>{formatDuration(call.duration_seconds)}</strong>
                        </div>
                        <div>
                            <span>Context version</span>
                            <strong>{call.context_version_used ?? "—"}</strong>
                        </div>
                        <div>
                            <span>Escalated</span>
                            <strong>{call.escalated ? "Yes" : "No"}</strong>
                        </div>
                    </div>
                    {call.summary ? (
                        <div className="quote-block">
                            <p className="summary-heading">Summary</p>
                            <p className="summary-body">{call.summary}</p>
                        </div>
                    ) : null}
                    {call.transcript ? (
                        <details className="transcript-details">
                            <summary>View transcript</summary>
                            <p className="summary-body">{call.transcript}</p>
                        </details>
                    ) : null}
                </div>
            ))}
        </div>
    );
}
