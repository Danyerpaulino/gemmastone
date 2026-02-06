"use client";

import { useEffect, useMemo, useState } from "react";

import { fetchJson } from "@/lib/api";
import type { LabResultOut, StoneAnalysisList } from "@/lib/types";

const STORAGE_KEY = "kidneystone_last_patient_id";

export default function LabUploadPanel({
    patientId: patientIdProp,
}: {
    patientId?: string;
} = {}) {
    const isControlled = patientIdProp !== undefined;
    const [patientId, setPatientId] = useState(patientIdProp ?? "");
    const [analysisId, setAnalysisId] = useState("");
    const [latestAnalysisId, setLatestAnalysisId] = useState<string | null>(null);
    const [resultType, setResultType] = useState("crystallography");
    const [resultDate, setResultDate] = useState("");
    const [resultsJson, setResultsJson] = useState("");
    const [rerun, setRerun] = useState(true);
    const [status, setStatus] = useState<
        "idle" | "loading" | "success" | "error"
    >("idle");
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
        }
    }, [isControlled]);

    useEffect(() => {
        if (!patientId) {
            setLatestAnalysisId(null);
            return;
        }

        let isActive = true;
        const loadLatest = async () => {
            const response = await fetchJson<StoneAnalysisList>(
                `/analyses/?patient_id=${patientId}&limit=1`
            );
            if (!isActive) {
                return;
            }
            if (response.error) {
                setLatestAnalysisId(null);
                return;
            }
            const latest = response.data?.items?.[0];
            setLatestAnalysisId(latest?.id || null);
        };

        loadLatest();

        return () => {
            isActive = false;
        };
    }, [patientId]);

    useEffect(() => {
        setAnalysisId("");
    }, [patientId]);

    const placeholder = useMemo(() => {
        if (resultType === "urine_24hr") {
            return '{"volume_ml_day":1700,"calcium_mg_day":320,"citrate_mg_day":250,"ph":5.3}';
        }
        return '{"composition":"calcium_oxalate","notes":"Calcium oxalate predominant"}';
    }, [resultType]);

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setStatus("loading");
        setMessage("");

        if (!patientId.trim()) {
            setStatus("error");
            setMessage("Patient ID is required.");
            return;
        }
        if (!resultsJson.trim()) {
            setStatus("error");
            setMessage("Results JSON is required.");
            return;
        }

        let parsed: Record<string, unknown>;
        try {
            parsed = JSON.parse(resultsJson);
        } catch (error) {
            setStatus("error");
            setMessage("Results must be valid JSON.");
            return;
        }

        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            setStatus("error");
            setMessage("Results JSON must be an object.");
            return;
        }

        const payload: Record<string, unknown> = {
            patient_id: patientId,
            result_type: resultType,
            results: parsed,
        };
        if (analysisId.trim()) {
            payload.analysis_id = analysisId.trim();
        }
        if (resultDate) {
            payload.result_date = resultDate;
        }

        const response = await fetchJson<LabResultOut>(
            `/labs?rerun=${rerun ? "true" : "false"}`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            }
        );

        if (response.error) {
            setStatus("error");
            setMessage(response.error);
            return;
        }

        setStatus("success");
        setMessage("Lab result saved.");
        if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, patientId);
        }
    };

    return (
        <div className="card">
            <div className="card-header">
                <h2>Labs upload</h2>
                <span className="badge">Live</span>
            </div>
            <p className="muted">
                Add crystallography or 24-hour urine results and optionally
                re-run the workflow.
            </p>

            <form className="stack" onSubmit={handleSubmit}>
                <div className="form-grid">
                    <label>
                        Patient ID
                        <input
                            value={patientId}
                            onChange={(event) => {
                                if (!isControlled) {
                                    setPatientId(event.target.value);
                                }
                            }}
                            placeholder="UUID"
                            disabled={isControlled}
                        />
                    </label>
                    <label>
                        Analysis ID (optional)
                        <input
                            value={analysisId}
                            onChange={(event) =>
                                setAnalysisId(event.target.value)
                            }
                            placeholder="UUID"
                        />
                    </label>
                </div>

                <div className="actions">
                    <button
                        type="button"
                        onClick={() =>
                            setAnalysisId(latestAnalysisId || "")
                        }
                        disabled={!latestAnalysisId}
                    >
                        Use latest analysis
                    </button>
                    <p className="status">
                        {latestAnalysisId
                            ? `Latest analysis: ${latestAnalysisId}`
                            : "No analysis found yet."}
                    </p>
                </div>

                <div className="form-grid">
                    <label>
                        Result type
                        <select
                            value={resultType}
                            onChange={(event) =>
                                setResultType(event.target.value)
                            }
                        >
                            <option value="crystallography">
                                Crystallography
                            </option>
                            <option value="urine_24hr">24-hour urine</option>
                        </select>
                    </label>
                    <label>
                        Result date (optional)
                        <input
                            type="date"
                            value={resultDate}
                            onChange={(event) =>
                                setResultDate(event.target.value)
                            }
                        />
                    </label>
                </div>

                <div className="form-grid single">
                    <label>
                        Results (JSON)
                        <textarea
                            rows={5}
                            value={resultsJson}
                            onChange={(event) =>
                                setResultsJson(event.target.value)
                            }
                            placeholder={placeholder}
                        />
                    </label>
                </div>

                <div className="actions">
                    <button type="submit" disabled={status === "loading"}>
                        {status === "loading"
                            ? "Submitting..."
                            : "Submit labs"}
                    </button>
                    <div className="pill">
                        <input
                            type="checkbox"
                            checked={rerun}
                            onChange={(event) => setRerun(event.target.checked)}
                        />
                        <span>Re-run workflow</span>
                    </div>
                    <p
                        className={`status ${
                            status === "error"
                                ? "error"
                                : status === "success"
                                ? "success"
                                : ""
                        }`}
                    >
                        {message || "Ready."}
                    </p>
                </div>
            </form>
        </div>
    );
}
