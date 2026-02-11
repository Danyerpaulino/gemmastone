"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchJson } from "@/lib/api";
import { logoutSession, useAuthSession } from "@/lib/auth";
import type { PatientOut } from "@/lib/types";

const navLinks = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/plan", label: "Plan" },
    { href: "/labs", label: "Labs" },
    { href: "/settings", label: "Settings" },
];

export default function PatientShell({ children }: { children: React.ReactNode }) {
    const router = useRouter();
    const { session, status } = useAuthSession({ required: true });
    const [patient, setPatient] = useState<PatientOut | null>(null);

    useEffect(() => {
        if (!session?.patientId) {
            return;
        }
        let active = true;
        const loadPatient = async () => {
            const response = await fetchJson<PatientOut>(`/patients/${session.patientId}`);
            if (!active) {
                return;
            }
            if (response.data) {
                setPatient(response.data);
            }
        };
        loadPatient();
        return () => {
            active = false;
        };
    }, [session?.patientId]);

    const handleLogout = async () => {
        await logoutSession();
        router.push("/login");
    };

    return (
        <div className="shell-top">
            <header className="topbar">
                <div className="topbar-left">
                    <Link href="/dashboard" className="brand">
                        <span className="brand-mark">KS</span>
                        <div>
                            <p className="brand-title">KidneyStones AI</p>
                            <p className="brand-subtitle">Prevention companion</p>
                        </div>
                    </Link>
                    <nav className="topbar-nav">
                        {navLinks.map((link) => (
                            <Link key={link.href} href={link.href} className="nav-pill">
                                {link.label}
                            </Link>
                        ))}
                    </nav>
                </div>
                <div className="topbar-actions">
                    <div className="user-chip">
                        <span className="status-dot" />
                        <div>
                            <p>{patient ? `${patient.first_name} ${patient.last_name}` : "Loading"}</p>
                            <span className="muted">Patient session</span>
                        </div>
                    </div>
                    <button type="button" className="ghost" onClick={handleLogout}>
                        Sign out
                    </button>
                </div>
            </header>

            {status === "loading" ? (
                <main className="page">
                    <div className="card">
                        <p className="status">Loading your dashboard...</p>
                    </div>
                </main>
            ) : status === "unauth" ? (
                <main className="page">
                    <div className="card">
                        <p className="status">Redirecting to login...</p>
                    </div>
                </main>
            ) : (
                <main className="page">{children}</main>
            )}
        </div>
    );
}
