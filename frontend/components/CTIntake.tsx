"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { useDemoGate } from "@/components/DemoGate";
import { fetchJson } from "@/lib/api";
import type { PatientList, PatientOut, ProviderList, ProviderOut } from "@/lib/types";

// Provider-facing CT intake form. Stores the latest workflow response locally for
// quick debugging; primary review screens now fetch live data from the API.

const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api";
const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";
const USE_SIGNED_UPLOADS =
    (process.env.NEXT_PUBLIC_USE_SIGNED_UPLOADS ??
        (API_URL.includes("localhost") ? "false" : "true")
    ).toLowerCase() === "true";
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
    const { requiresGate, lock } = useDemoGate();
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
    const [providers, setProviders] = useState<ProviderOut[]>([]);
    const [patients, setPatients] = useState<PatientOut[]>([]);
    const [directoryStatus, setDirectoryStatus] = useState<
        "idle" | "loading" | "error"
    >("idle");
    const [directoryMessage, setDirectoryMessage] = useState("");
    const [createProviderStatus, setCreateProviderStatus] = useState<
        "idle" | "saving" | "success" | "error"
    >("idle");
    const [createProviderMessage, setCreateProviderMessage] = useState("");
    const [createPatientStatus, setCreatePatientStatus] = useState<
        "idle" | "saving" | "success" | "error"
    >("idle");
    const [createPatientMessage, setCreatePatientMessage] = useState("");
    const [providerForm, setProviderForm] = useState({
        name: "",
        email: "",
        npi: "",
        specialty: "",
        practice_name: "",
    });
    const [patientForm, setPatientForm] = useState({
        first_name: "",
        last_name: "",
        email: "",
        phone: "",
        mrn: "",
    });

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

    useEffect(() => {
        let isActive = true;
        const loadDirectory = async () => {
            setDirectoryStatus("loading");
            setDirectoryMessage("");

            const [providerResponse, patientResponse] = await Promise.all([
                fetchJson<ProviderList>("/providers/?limit=200"),
                fetchJson<PatientList>("/patients/?limit=200"),
            ]);

            if (!isActive) {
                return;
            }

            if (providerResponse.error || patientResponse.error) {
                setDirectoryStatus("error");
                setDirectoryMessage(
                    providerResponse.error ||
                        patientResponse.error ||
                        "Unable to load directory."
                );
                setProviders(providerResponse.data?.items || []);
                setPatients(patientResponse.data?.items || []);
                return;
            }

            setProviders(providerResponse.data?.items || []);
            setPatients(patientResponse.data?.items || []);
            setDirectoryStatus("idle");
        };

        loadDirectory();

        return () => {
            isActive = false;
        };
    }, []);

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

    const filteredPatients = useMemo(() => {
        if (!providerId) {
            return patients;
        }
        return patients.filter((patient) => patient.provider_id === providerId);
    }, [patients, providerId]);

    const refreshDirectory = async () => {
        setDirectoryStatus("loading");
        setDirectoryMessage("");

        const [providerResponse, patientResponse] = await Promise.all([
            fetchJson<ProviderList>("/providers/?limit=200"),
            fetchJson<PatientList>("/patients/?limit=200"),
        ]);

        if (providerResponse.error || patientResponse.error) {
            setDirectoryStatus("error");
            setDirectoryMessage(
                providerResponse.error ||
                    patientResponse.error ||
                    "Unable to load directory."
            );
            setProviders(providerResponse.data?.items || []);
            setPatients(patientResponse.data?.items || []);
            return;
        }

        setProviders(providerResponse.data?.items || []);
        setPatients(patientResponse.data?.items || []);
        setDirectoryStatus("idle");
    };

    const handleCreateProvider = async (
        event: React.FormEvent<HTMLFormElement>
    ) => {
        event.preventDefault();
        setCreateProviderStatus("saving");
        setCreateProviderMessage("");

        if (!providerForm.name.trim() || !providerForm.email.trim()) {
            setCreateProviderStatus("error");
            setCreateProviderMessage("Provider name and email are required.");
            return;
        }

        const payload = {
            name: providerForm.name.trim(),
            email: providerForm.email.trim(),
            npi: providerForm.npi.trim() || null,
            specialty: providerForm.specialty.trim() || null,
            practice_name: providerForm.practice_name.trim() || null,
        };

        const response = await fetchJson<ProviderOut>("/providers/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (response.error || !response.data) {
            setCreateProviderStatus("error");
            setCreateProviderMessage(response.error || "Unable to create provider.");
            return;
        }

        setProviderId(response.data.id);
        setProviderForm({
            name: "",
            email: "",
            npi: "",
            specialty: "",
            practice_name: "",
        });
        setCreateProviderStatus("success");
        setCreateProviderMessage("Provider created.");
        refreshDirectory();
    };

    const handleCreatePatient = async (
        event: React.FormEvent<HTMLFormElement>
    ) => {
        event.preventDefault();
        setCreatePatientStatus("saving");
        setCreatePatientMessage("");

        if (!patientForm.first_name.trim() || !patientForm.last_name.trim()) {
            setCreatePatientStatus("error");
            setCreatePatientMessage("Patient first and last name are required.");
            return;
        }

        const payload: Record<string, unknown> = {
            first_name: patientForm.first_name.trim(),
            last_name: patientForm.last_name.trim(),
        };
        if (providerId) {
            payload.provider_id = providerId;
        }
        if (patientForm.email.trim()) {
            payload.email = patientForm.email.trim();
        }
        if (patientForm.phone.trim()) {
            payload.phone = patientForm.phone.trim();
        }
        if (patientForm.mrn.trim()) {
            payload.mrn = patientForm.mrn.trim();
        }

        const response = await fetchJson<PatientOut>("/patients/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        if (response.error || !response.data) {
            setCreatePatientStatus("error");
            setCreatePatientMessage(response.error || "Unable to create patient.");
            return;
        }

        setPatientId(response.data.id);
        setPatientForm({
            first_name: "",
            last_name: "",
            email: "",
            phone: "",
            mrn: "",
        });
        setCreatePatientStatus("success");
        setCreatePatientMessage("Patient created.");
        refreshDirectory();
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
                        {requiresGate ? (
                            <button
                                type="button"
                                className="ghost"
                                onClick={lock}
                            >
                                Lock demo
                            </button>
                        ) : null}
                    </div>
                </header>
            )}

            <section className="grid">
                <div className="card">
                    <h2>Provider + patient setup</h2>
                    <p className="muted">
                        Select existing records or create new ones before you
                        run the CT workflow.
                    </p>

                    <div className="form-grid">
                        <label>
                            Existing provider
                            <select
                                value={providerId}
                                onChange={(event) =>
                                    setProviderId(event.target.value)
                                }
                            >
                                <option value="">Select provider</option>
                                {providers.map((provider) => (
                                    <option
                                        key={provider.id}
                                        value={provider.id}
                                    >
                                        {provider.name} ({provider.email})
                                    </option>
                                ))}
                            </select>
                        </label>
                        <label>
                            Existing patient
                            <select
                                value={patientId}
                                onChange={(event) =>
                                    setPatientId(event.target.value)
                                }
                            >
                                <option value="">Select patient</option>
                                {filteredPatients.map((patient) => (
                                    <option key={patient.id} value={patient.id}>
                                        {patient.first_name} {patient.last_name}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>

                    <div className="actions">
                        <button
                            type="button"
                            onClick={refreshDirectory}
                            disabled={directoryStatus === "loading"}
                        >
                            {directoryStatus === "loading"
                                ? "Refreshing..."
                                : "Refresh list"}
                        </button>
                        <p
                            className={`status ${
                                directoryStatus === "error" ? "error" : ""
                            }`}
                        >
                            {directoryStatus === "loading"
                                ? "Loading directory..."
                                : directoryMessage ||
                                  `${providers.length} providers · ${patients.length} patients`}
                        </p>
                    </div>

                    <div className="pill">
                        New patients attach to the selected provider ID.
                    </div>

                    <h3>Create provider</h3>
                    <form className="form-grid" onSubmit={handleCreateProvider}>
                        <label>
                            Provider name
                            <input
                                value={providerForm.name}
                                onChange={(event) =>
                                    setProviderForm((current) => ({
                                        ...current,
                                        name: event.target.value,
                                    }))
                                }
                                placeholder="Dr. Ilya Sobol"
                                required
                            />
                        </label>
                        <label>
                            Provider email
                            <input
                                type="email"
                                value={providerForm.email}
                                onChange={(event) =>
                                    setProviderForm((current) => ({
                                        ...current,
                                        email: event.target.value,
                                    }))
                                }
                                placeholder="provider@clinic.org"
                                required
                            />
                        </label>
                        <label>
                            NPI (optional)
                            <input
                                value={providerForm.npi}
                                onChange={(event) =>
                                    setProviderForm((current) => ({
                                        ...current,
                                        npi: event.target.value,
                                    }))
                                }
                                placeholder="1234567890"
                            />
                        </label>
                        <label>
                            Specialty (optional)
                            <input
                                value={providerForm.specialty}
                                onChange={(event) =>
                                    setProviderForm((current) => ({
                                        ...current,
                                        specialty: event.target.value,
                                    }))
                                }
                                placeholder="Urology"
                            />
                        </label>
                        <label>
                            Practice name (optional)
                            <input
                                value={providerForm.practice_name}
                                onChange={(event) =>
                                    setProviderForm((current) => ({
                                        ...current,
                                        practice_name: event.target.value,
                                    }))
                                }
                                placeholder="KidneyStone AI Clinic"
                            />
                        </label>
                        <div className="actions">
                            <button
                                type="submit"
                                disabled={createProviderStatus === "saving"}
                            >
                                {createProviderStatus === "saving"
                                    ? "Creating..."
                                    : "Create provider"}
                            </button>
                            <p
                                className={`status ${
                                    createProviderStatus === "error"
                                        ? "error"
                                        : createProviderStatus === "success"
                                        ? "success"
                                        : ""
                                }`}
                            >
                                {createProviderMessage || " "}
                            </p>
                        </div>
                    </form>

                    <h3>Create patient</h3>
                    <form className="form-grid" onSubmit={handleCreatePatient}>
                        <label>
                            First name
                            <input
                                value={patientForm.first_name}
                                onChange={(event) =>
                                    setPatientForm((current) => ({
                                        ...current,
                                        first_name: event.target.value,
                                    }))
                                }
                                placeholder="Jamie"
                                required
                            />
                        </label>
                        <label>
                            Last name
                            <input
                                value={patientForm.last_name}
                                onChange={(event) =>
                                    setPatientForm((current) => ({
                                        ...current,
                                        last_name: event.target.value,
                                    }))
                                }
                                placeholder="Stone"
                                required
                            />
                        </label>
                        <label>
                            Email (optional)
                            <input
                                type="email"
                                value={patientForm.email}
                                onChange={(event) =>
                                    setPatientForm((current) => ({
                                        ...current,
                                        email: event.target.value,
                                    }))
                                }
                                placeholder="patient@demo.org"
                            />
                        </label>
                        <label>
                            Phone (optional)
                            <input
                                value={patientForm.phone}
                                onChange={(event) =>
                                    setPatientForm((current) => ({
                                        ...current,
                                        phone: event.target.value,
                                    }))
                                }
                                placeholder="+1 555 555 0123"
                            />
                        </label>
                        <label>
                            MRN (optional)
                            <input
                                value={patientForm.mrn}
                                onChange={(event) =>
                                    setPatientForm((current) => ({
                                        ...current,
                                        mrn: event.target.value,
                                    }))
                                }
                                placeholder="DEMO-0001"
                            />
                        </label>
                        <div className="actions">
                            <button
                                type="submit"
                                disabled={createPatientStatus === "saving"}
                            >
                                {createPatientStatus === "saving"
                                    ? "Creating..."
                                    : "Create patient"}
                            </button>
                            <p
                                className={`status ${
                                    createPatientStatus === "error"
                                        ? "error"
                                        : createPatientStatus === "success"
                                        ? "success"
                                        : ""
                                }`}
                            >
                                {createPatientMessage || " "}
                            </p>
                        </div>
                    </form>
                </div>
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
