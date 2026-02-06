"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

// Provider-facing CT intake form. Stores the latest workflow response locally for
// quick debugging; primary review screens now fetch live data from the API.

const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";
const USE_SIGNED_UPLOADS =
    (process.env.NEXT_PUBLIC_USE_SIGNED_UPLOADS ??
        (API_URL.includes("localhost") ? "false" : "true")
    ).toLowerCase() === "true";
const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "";
const DEMO_PROVIDER_ID = process.env.NEXT_PUBLIC_DEMO_PROVIDER_ID || "";
const DEMO_PATIENT_ID = process.env.NEXT_PUBLIC_DEMO_PATIENT_ID || "";

const DEMO_CRYSTALLOGRAPHY =
    '{"composition":"calcium_oxalate","notes":"Calcium oxalate monohydrate predominant"}';
const DEMO_URINE =
    '{"volume_ml_day":1700,"calcium_mg_day":320,"citrate_mg_day":250,"uric_acid_mg_day":820,"ph":5.3,"sodium_mg_day":2400}';

const STORAGE_KEYS = {
    analysis: "kidneystone_latest_analysis",
    patient: "kidneystone_last_patient_id",
    provider: "kidneystone_last_provider_id",
};

const rememberLatest = (payload: unknown, patientId: string, providerId: string) => {
    if (typeof window === "undefined") {
        return;
    }
    window.localStorage.setItem(STORAGE_KEYS.analysis, JSON.stringify(payload));
    window.localStorage.setItem(STORAGE_KEYS.patient, patientId);
    window.localStorage.setItem(STORAGE_KEYS.provider, providerId);
};

export default function CTIntake({
    eyebrow = "Provider portal",
    title = "KidneyStone AI Intake",
    subtitle =
        "Upload a CT, attach labs, and generate a treatment and prevention plan in one pass.",
    hideHero = false,
}: {
    eyebrow?: string;
    title?: string;
    subtitle?: string;
    hideHero?: boolean;
}) {
    const accessKey = "kidneystone_demo_access_v1";
    const accessToken = useMemo(
        () => (DEMO_PASSWORD ? `v1:${btoa(DEMO_PASSWORD)}` : ""),
        [DEMO_PASSWORD]
    );
    const [isUnlocked, setIsUnlocked] = useState(!DEMO_PASSWORD);
    const [accessInput, setAccessInput] = useState("");
    const [accessError, setAccessError] = useState("");
    const [providerId, setProviderId] = useState("");
    const [patientId, setPatientId] = useState("");
    const [ctFile, setCtFile] = useState<File | null>(null);
    const [crystallographyJson, setCrystallographyJson] = useState("");
    const [urineJson, setUrineJson] = useState("");
    const [demoMode, setDemoMode] = useState(false);
    const [backupValues, setBackupValues] = useState<{
        providerId: string;
        patientId: string;
        crystallographyJson: string;
        urineJson: string;
    } | null>(null);
    const [status, setStatus] = useState<"idle" | "submitting" | "success" | "error">(
        "idle"
    );
    const [message, setMessage] = useState("");
    const [resultJson, setResultJson] = useState("");
    const [resultData, setResultData] = useState<any>(null);

    useEffect(() => {
        if (!DEMO_PASSWORD) {
            setIsUnlocked(true);
            return;
        }
        const saved = window.localStorage.getItem(accessKey);
        if (saved === accessToken) {
            setIsUnlocked(true);
        }
    }, [accessKey, accessToken]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const storedPatient = window.localStorage.getItem(STORAGE_KEYS.patient);
        const storedProvider = window.localStorage.getItem(STORAGE_KEYS.provider);
        if (storedPatient) {
            setPatientId(storedPatient);
        }
        if (storedProvider) {
            setProviderId(storedProvider);
        }
    }, []);

    const handleUnlock = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!DEMO_PASSWORD) {
            setIsUnlocked(true);
            return;
        }
        if (accessInput.trim() === DEMO_PASSWORD) {
            window.localStorage.setItem(accessKey, accessToken);
            setIsUnlocked(true);
            setAccessError("");
        } else {
            setAccessError("Incorrect access code. Try again.");
        }
    };

    const handleLock = () => {
        window.localStorage.removeItem(accessKey);
        setIsUnlocked(false);
        setAccessInput("");
        setAccessError("");
    };

    const toggleDemoMode = () => {
        if (!demoMode) {
            setBackupValues({
                providerId,
                patientId,
                crystallographyJson,
                urineJson,
            });
            setProviderId(DEMO_PROVIDER_ID);
            setPatientId(DEMO_PATIENT_ID);
            setCrystallographyJson(DEMO_CRYSTALLOGRAPHY);
            setUrineJson(DEMO_URINE);
            setDemoMode(true);
        } else {
            if (backupValues) {
                setProviderId(backupValues.providerId);
                setPatientId(backupValues.patientId);
                setCrystallographyJson(backupValues.crystallographyJson);
                setUrineJson(backupValues.urineJson);
            } else {
                setProviderId("");
                setPatientId("");
                setCrystallographyJson("");
                setUrineJson("");
            }
            setDemoMode(false);
        }
    };

    const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setStatus("submitting");
        setMessage("");
        setResultJson("");
        setResultData(null);

        if (!ctFile) {
            setStatus("error");
            setMessage("Please attach a CT zip or DICOM file.");
            return;
        }
        if (!providerId || !patientId) {
            setStatus("error");
            setMessage("Provider ID and Patient ID are required.");
            return;
        }

        try {
            const authHeaders: Record<string, string> = {};
            if (API_TOKEN) {
                authHeaders.Authorization = `Bearer ${API_TOKEN}`;
            }

            let crystallographyPayload: Record<string, unknown> | undefined;
            let urinePayload: Record<string, unknown> | undefined;

            if (crystallographyJson.trim()) {
                const parsed = JSON.parse(crystallographyJson);
                if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
                    throw new Error("Crystallography JSON must be an object.");
                }
                crystallographyPayload = parsed as Record<string, unknown>;
            }
            if (urineJson.trim()) {
                const parsed = JSON.parse(urineJson);
                if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
                    throw new Error("24hr urine JSON must be an object.");
                }
                urinePayload = parsed as Record<string, unknown>;
            }

            let payload: any = null;
            if (USE_SIGNED_UPLOADS) {
                const signResponse = await fetch(`${API_URL}/ct/sign-upload`, {
                    method: "POST",
                    headers: {
                        ...authHeaders,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        filename: ctFile.name,
                        content_type:
                            ctFile.type || "application/octet-stream",
                        size_bytes: ctFile.size,
                    }),
                });
                const signPayload = await signResponse.json();
                if (!signResponse.ok) {
                    throw new Error(
                        signPayload?.detail ||
                            "Unable to create signed upload URL."
                    );
                }

                const uploadResponse = await fetch(signPayload.upload_url, {
                    method: "PUT",
                    headers: signPayload.headers || {
                        "Content-Type":
                            ctFile.type || "application/octet-stream",
                    },
                    body: ctFile,
                });
                if (!uploadResponse.ok) {
                    throw new Error("Upload to storage failed.");
                }

                const analyzeResponse = await fetch(
                    `${API_URL}/ct/analyze-uri`,
                    {
                        method: "POST",
                        headers: {
                            ...authHeaders,
                            "Content-Type": "application/json",
                        },
                        body: JSON.stringify({
                            gcs_uri: signPayload.gcs_uri,
                            provider_id: providerId,
                            patient_id: patientId,
                            crystallography_results: crystallographyPayload,
                            urine_24hr_results: urinePayload,
                        }),
                    }
                );
                payload = await analyzeResponse.json();
                if (!analyzeResponse.ok) {
                    throw new Error(
                        payload?.detail || "CT analysis failed."
                    );
                }
            } else {
                const formData = new FormData();
                formData.append("file", ctFile);
                formData.append("provider_id", providerId);
                formData.append("patient_id", patientId);
                if (crystallographyPayload) {
                    formData.append(
                        "crystallography_results",
                        JSON.stringify(crystallographyPayload)
                    );
                }
                if (urinePayload) {
                    formData.append(
                        "urine_24hr_results",
                        JSON.stringify(urinePayload)
                    );
                }

                const response = await fetch(`${API_URL}/ct/analyze`, {
                    method: "POST",
                    body: formData,
                    headers: authHeaders,
                });
                payload = await response.json();

                if (!response.ok) {
                    throw new Error(payload?.detail || "CT analysis failed.");
                }
            }

            setStatus("success");
            setMessage("Analysis complete.");
            setResultJson(JSON.stringify(payload, null, 2));
            setResultData(payload);
            rememberLatest(payload, patientId, providerId);
        } catch (error) {
            const message =
                error instanceof Error ? error.message : "Unexpected error.";
            setStatus("error");
            setMessage(message);
        }
    };

    if (DEMO_PASSWORD && !isUnlocked) {
        return (
            <section className="card auth-card">
                <p className="eyebrow">Demo access</p>
                <h1>Enter the shared access code</h1>
                <p className="lead">
                    This public demo is gated for the competition review team.
                    Ask the project owner for the access code.
                </p>
                <form className="auth-form" onSubmit={handleUnlock}>
                    <label>
                        Access code
                        <input
                            type="password"
                            value={accessInput}
                            onChange={(event) =>
                                setAccessInput(event.target.value)
                            }
                            placeholder="Shared demo code"
                            required
                        />
                    </label>
                    <div className="actions auth-actions">
                        <button type="submit">Unlock</button>
                        <p className="status error">{accessError || " "}</p>
                    </div>
                </form>
            </section>
        );
    }

    return (
        <>
            {!hideHero && (
                <header className="hero">
                    <div>
                        <p className="eyebrow">{eyebrow}</p>
                        <h1>{title}</h1>
                        <p className="lead">{subtitle}</p>
                    </div>
                    <div className="hero-card">
                        <p className="hero-title">Quick start</p>
                        <ol>
                            <li>Seed demo data in the backend.</li>
                            <li>Paste Provider + Patient IDs.</li>
                            <li>Upload a CT and optional labs.</li>
                        </ol>
                        {DEMO_PASSWORD ? (
                            <button
                                type="button"
                                className="ghost"
                                onClick={handleLock}
                            >
                                Lock demo
                            </button>
                        ) : null}
                    </div>
                </header>
            )}

            <section className="grid">
                <form className="card" onSubmit={handleSubmit}>
                    <h2>CT + Labs</h2>
                    <div className="demo-toggle">
                        <button
                            className={`toggle ${demoMode ? "on" : ""}`}
                            type="button"
                            onClick={toggleDemoMode}
                        >
                            {demoMode ? "Demo mode on" : "Demo mode off"}
                        </button>
                        <p>
                            {DEMO_PROVIDER_ID && DEMO_PATIENT_ID
                                ? "Uses demo IDs from env."
                                : "Set NEXT_PUBLIC_DEMO_PROVIDER_ID and NEXT_PUBLIC_DEMO_PATIENT_ID for auto-fill."}
                        </p>
                    </div>
                    <div className="form-grid">
                        <label>
                            Provider ID
                            <input
                                value={providerId}
                                onChange={(event) =>
                                    setProviderId(event.target.value)
                                }
                                placeholder="UUID"
                                required
                            />
                        </label>
                        <label>
                            Patient ID
                            <input
                                value={patientId}
                                onChange={(event) =>
                                    setPatientId(event.target.value)
                                }
                                placeholder="UUID"
                                required
                            />
                        </label>
                        <label className="file">
                            CT upload
                            <input
                                type="file"
                                accept=".zip,.dcm"
                                onChange={(event) =>
                                    setCtFile(
                                        event.target.files?.[0] || null
                                    )
                                }
                            />
                            <span>
                                {ctFile
                                    ? ctFile.name
                                    : "Choose zip or DICOM file"}
                            </span>
                        </label>
                    </div>

                    <div className="form-grid single">
                        <label>
                            Crystallography (JSON)
                            <textarea
                                value={crystallographyJson}
                                onChange={(event) =>
                                    setCrystallographyJson(event.target.value)
                                }
                                placeholder='{"composition":"calcium_oxalate"}'
                                rows={5}
                            />
                        </label>
                        <label>
                            24hr Urine (JSON)
                            <textarea
                                value={urineJson}
                                onChange={(event) =>
                                    setUrineJson(event.target.value)
                                }
                                placeholder='{"calcium_mg_day":320,"citrate_mg_day":250,"ph":5.3}'
                                rows={5}
                            />
                        </label>
                    </div>

                    <div className="actions">
                        <button
                            type="submit"
                            disabled={status === "submitting"}
                        >
                            {status === "submitting"
                                ? "Analyzing..."
                                : "Run analysis"}
                        </button>
                        <p className={`status ${status}`}>
                            {message || "Ready."}
                        </p>
                    </div>
                </form>

                <div className="card note">
                    <h2>Lab rules</h2>
                    <p>
                        If you leave the lab fields empty, the backend will pull
                        the latest lab results on file for the patient.
                    </p>
                    <p>
                        {USE_SIGNED_UPLOADS
                            ? "Large CTs upload directly to GCS via signed URL."
                            : "Signed uploads are disabled for this environment."}
                    </p>
                    <div className="pill">
                        API target: <span>{API_URL}</span>
                    </div>
                    <div className="example">
                        <p>Sample urine JSON</p>
                        <code>
                            {"{ \"calcium_mg_day\": 320, \"citrate_mg_day\": 250, \"ph\": 5.3 }"}
                        </code>
                    </div>
                    <div className="link-stack">
                        <Link href="/dashboard">Provider dashboard</Link>
                        <Link href="/chat">Patient chat</Link>
                    </div>
                </div>
            </section>

            <section className="grid results-grid">
                <div className="card">
                    <h2>Plan preview</h2>
                    {resultData?.prevention_plan ? (
                        <div className="preview">
                            <p>
                                <strong>Fluid target:</strong>{" "}
                                {resultData.prevention_plan
                                    .fluid_intake_target_ml || "N/A"} ml/day
                            </p>
                            <p>
                                <strong>Treatment:</strong>{" "}
                                {resultData.analysis
                                    ?.treatment_recommendation || "N/A"}
                            </p>
                            <p>
                                <strong>Urgency:</strong>{" "}
                                {resultData.analysis?.urgency_level || "N/A"}
                            </p>
                            <div className="preview-block">
                                <span>Dietary guidance</span>
                                <p>
                                    {resultData.prevention_plan
                                        .dietary_recommendations?.length
                                        ? `${resultData.prevention_plan.dietary_recommendations.length} categories`
                                        : "None"}
                                </p>
                            </div>
                            <div className="preview-block">
                                <span>Medications</span>
                                <p>
                                    {resultData.prevention_plan
                                        .medications_recommended?.length
                                        ? resultData.prevention_plan.medications_recommended
                                              .map((med: any) => med.name)
                                              .join(", ")
                                        : "None"}
                                </p>
                            </div>
                            <div className="preview-block">
                                <span>Lifestyle</span>
                                <p>
                                    {resultData.prevention_plan
                                        .lifestyle_modifications?.length
                                        ? `${resultData.prevention_plan.lifestyle_modifications.length} items`
                                        : "None"}
                                </p>
                            </div>
                        </div>
                    ) : (
                        <p className="empty">No plan yet. Run an analysis.</p>
                    )}
                </div>
                <div className="card">
                    <h2>Nudges preview</h2>
                    {resultData?.nudges?.length ? (
                        <ul className="nudges">
                            {resultData.nudges
                                .slice(0, 3)
                                .map((nudge: any) => (
                                    <li
                                        key={
                                            nudge.id || nudge.scheduled_time
                                        }
                                    >
                                        <p>{nudge.message_content}</p>
                                        <span>
                                            {nudge.scheduled_time
                                                ? new Date(
                                                      nudge.scheduled_time
                                                  ).toLocaleString()
                                                : "Scheduled time TBD"}
                                        </span>
                                    </li>
                                ))}
                        </ul>
                    ) : (
                        <p className="empty">No nudges yet. Run an analysis.</p>
                    )}
                </div>
            </section>

            <section className="card result">
                <h2>Latest response</h2>
                <pre>{resultJson || "Run an analysis to see results."}</pre>
            </section>
        </>
    );
}
