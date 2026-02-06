"use client";

import { useEffect, useMemo, useState } from "react";

import LatestPlanPreview from "@/components/LatestPlanPreview";
import { fetchJson } from "@/lib/api";
import type { PatientList, PatientOut } from "@/lib/types";

const STORAGE_KEY = "kidneystone_last_patient_id";

export default function PatientPlanWorkspace() {
    const [patientId, setPatientId] = useState("");
    const [patients, setPatients] = useState<PatientOut[]>([]);
    const [directoryStatus, setDirectoryStatus] = useState<
        "idle" | "loading" | "error"
    >("idle");
    const [directoryMessage, setDirectoryMessage] = useState("");

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

    const handlePatientIdChange = (value: string) => {
        setPatientId(value);
        if (typeof window !== "undefined") {
            if (value.trim()) {
                window.localStorage.setItem(STORAGE_KEY, value);
            } else {
                window.localStorage.removeItem(STORAGE_KEY);
            }
        }
    };

    return (
        <div className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Choose patient</h2>
                </div>
                <div className="form-grid">
                    <label>
                        Patient
                        <select
                            value={patientId}
                            onChange={(event) =>
                                handlePatientIdChange(event.target.value)
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
            </div>

            <LatestPlanPreview patientId={patientId} />
        </div>
    );
}
