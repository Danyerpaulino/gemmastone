import Link from "next/link";

import { fetchJson } from "@/lib/api";
import type { PatientList } from "@/lib/types";

export default async function PatientsPage() {
    const patients = await fetchJson<PatientList>("/patients?limit=50");

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Patients</h2>
                    <Link className="text-link" href="/upload">
                        Run CT intake
                    </Link>
                </div>
                <p className="muted">
                    Review patient records, open the latest analysis, and approve
                    prevention plans.
                </p>
            </div>

            <div className="card">
                {patients.data?.items?.length ? (
                    <div className="table">
                        <div className="table-head">
                            <span>Patient</span>
                            <span>MRN</span>
                            <span>Email</span>
                            <span>Phone</span>
                            <span></span>
                        </div>
                        {patients.data.items.map((patient) => (
                            <div className="table-row" key={patient.id}>
                                <span>
                                    {patient.first_name} {patient.last_name}
                                </span>
                                <span>{patient.mrn || "—"}</span>
                                <span>{patient.email || "—"}</span>
                                <span>{patient.phone || "—"}</span>
                                <Link
                                    className="text-link"
                                    href={`/patients/${patient.id}`}
                                >
                                    View
                                </Link>
                            </div>
                        ))}
                    </div>
                ) : (
                    <p className="empty">
                        {patients.error
                            ? `Unable to load patients: ${patients.error}`
                            : "No patients found yet."}
                    </p>
                )}
            </div>
        </section>
    );
}
