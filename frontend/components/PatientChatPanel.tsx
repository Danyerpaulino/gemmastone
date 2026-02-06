"use client";

import { useEffect, useMemo, useState } from "react";

import { API_TOKEN, API_URL } from "@/lib/api";

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
    const [chat, setChat] = useState<ChatMessage[]>([{
        role: "assistant",
        text: "Hi! I can answer questions about your prevention plan and hydration goals. How can I help today?",
    }]);

    const apiBase = useMemo(() => API_URL.replace(/\/$/, ""), []);

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
            setPatientId(stored);
        }
    }, []);

    const sendMessage = async () => {
        if (!patientId.trim()) {
            setStatus("error");
            setError("Enter a patient ID to start the chat.");
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
                    Patient ID
                    <input
                        value={patientId}
                        onChange={(event) => setPatientId(event.target.value)}
                        placeholder="UUID"
                    />
                </label>
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
