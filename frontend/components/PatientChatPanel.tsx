"use client";

import { useEffect, useMemo, useState } from "react";

import { API_TOKEN, API_URL, fetchJson } from "@/lib/api";
import type { PatientList, PatientOut } from "@/lib/types";

// Patient-facing chat panel wired to MedGemma via the backend /patients/{id}/chat endpoint.
// This is the only live engagement channel in the public demo.
type ChatMessage = {
    role: "patient" | "assistant";
    text: string;
};

const STORAGE_KEY = "kidneystone_last_patient_id";

export default function PatientChatPanel() {
    const [patientId, setPatientId] = useState("");
    const [message, setMessage] = useState("");
    const [status, setStatus] = useState<"idle" | "sending" | "error">("idle");
    const [error, setError] = useState("");
    const [patients, setPatients] = useState<PatientOut[]>([]);
    const [directoryStatus, setDirectoryStatus] = useState<
        "idle" | "loading" | "error"
    >("idle");
    const [directoryMessage, setDirectoryMessage] = useState("");
    const [chat, setChat] = useState<ChatMessage[]>([{
        role: "assistant",
        text: "Hi! I can answer questions about your prevention plan and hydration goals. How can I help today?",
    }]);

    const apiBase = useMemo(() => API_URL.replace(/\/$/, ""), []);
    const orderedPatients = useMemo(() => {
        return [...patients].sort((a, b) => {
            const last = a.last_name.localeCompare(b.last_name);
            if (last !== 0) {
                return last;
            }
            return a.first_name.localeCompare(b.first_name);
        });
    }, [patients]);
    const selectedPatientMissing = useMemo(() => {
        if (!patientId) {
            return false;
        }
        return !patients.some((patient) => patient.id === patientId);
    }, [patientId, patients]);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
            setPatientId(stored);
        }
    }, []);

    useEffect(() => {
        let isActive = true;

        const loadPatients = async () => {
            setDirectoryStatus("loading");
            setDirectoryMessage("");

            const response = await fetchJson<PatientList>("/patients/?limit=200");
            if (!isActive) {
                return;
            }

            if (response.error) {
                setDirectoryStatus("error");
                setDirectoryMessage(response.error || "Unable to load patients.");
                setPatients(response.data?.items || []);
                return;
            }

            setPatients(response.data?.items || []);
            setDirectoryStatus("idle");
        };

        loadPatients();

        return () => {
            isActive = false;
        };
    }, []);

    const refreshPatients = async () => {
        setDirectoryStatus("loading");
        setDirectoryMessage("");

        const response = await fetchJson<PatientList>("/patients/?limit=200");
        if (response.error) {
            setDirectoryStatus("error");
            setDirectoryMessage(response.error || "Unable to load patients.");
            setPatients(response.data?.items || []);
            return;
        }

        setPatients(response.data?.items || []);
        setDirectoryStatus("idle");
    };

    const handlePatientChange = (value: string) => {
        setPatientId(value);
        setError("");
        setStatus((current) => (current === "sending" ? current : "idle"));
        if (typeof window !== "undefined") {
            if (value.trim()) {
                window.localStorage.setItem(STORAGE_KEY, value);
            } else {
                window.localStorage.removeItem(STORAGE_KEY);
            }
        }
    };

    const sendMessage = async () => {
        if (!patientId.trim()) {
            setStatus("error");
            setError("Select a patient to start the chat.");
            return;
        }
        if (!message.trim()) {
            return;
        }
        setStatus("sending");
        setError("");

        const next = message.trim();
        setChat((current) => [...current, { role: "patient", text: next }]);
        setMessage("");

        try {
        const response = await fetch(`${apiBase}/patients/${patientId}/chat`, {
            method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
                },
                body: JSON.stringify({ message: next }),
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload?.detail || "Chat request failed.");
            }
            setChat((current) => [
                ...current,
                { role: "assistant", text: payload.response || "" },
            ]);
            if (payload.escalated) {
                setChat((current) => [
                    ...current,
                    {
                        role: "assistant",
                        text: "This sounds urgent. Please contact your care team right away.",
                    },
                ]);
            }
            setStatus("idle");
        } catch (error) {
            setStatus("error");
            setError(
                error instanceof Error ? error.message : "Unable to reach chat."
            );
        }

        if (typeof window !== "undefined") {
            window.localStorage.setItem(STORAGE_KEY, patientId);
        }
    };

    return (
        <div className="card chat-card">
            <div className="card-header">
                <h2>Patient chat</h2>
                <span className="badge">MedGemma live</span>
            </div>
            <div className="form-grid">
                <label>
                    Patient
                    <select
                        value={patientId}
                        onChange={(event) =>
                            handlePatientChange(event.target.value)
                        }
                    >
                        <option value="">Select patient</option>
                        {selectedPatientMissing ? (
                            <option value={patientId}>
                                Saved patient (not in list)
                            </option>
                        ) : null}
                        {orderedPatients.map((patient) => (
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
                    onClick={refreshPatients}
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
                        ? "Loading patients..."
                        : directoryMessage ||
                          `${patients.length} patients`}
                </p>
            </div>
            <div className="chat-window">
                {chat.map((entry, index) => (
                    <div
                        key={`${entry.role}-${index}`}
                        className={`chat-message ${entry.role}`}
                    >
                        <p>{entry.text}</p>
                    </div>
                ))}
            </div>
            <div className="chat-input">
                <textarea
                    rows={2}
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                    placeholder="Ask about hydration, diet, or symptoms..."
                />
                <button
                    type="button"
                    onClick={sendMessage}
                    disabled={status === "sending"}
                >
                    {status === "sending" ? "Sending..." : "Send"}
                </button>
            </div>
            {status === "error" ? <p className="status error">{error}</p> : null}
        </div>
    );
}
