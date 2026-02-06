"use client";

import { useEffect, useState } from "react";

import LatestPlanPreview from "@/components/LatestPlanPreview";
import PatientPlanPanel from "@/components/PatientPlanPanel";

const STORAGE_KEY = "kidneystone_last_patient_id";

export default function PatientPlanWorkspace() {
    const [patientId, setPatientId] = useState("");

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }
        const stored = window.localStorage.getItem(STORAGE_KEY);
        if (stored) {
            setPatientId(stored);
        }
    }, []);

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
        <div className="grid">
            <PatientPlanPanel
                patientId={patientId}
                onPatientIdChange={handlePatientIdChange}
            />
            <LatestPlanPreview patientId={patientId} />
        </div>
    );
}
