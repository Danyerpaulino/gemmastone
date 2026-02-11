import Link from "next/link";

import LabUploadPanel from "@/components/LabUploadPanel";

export default async function PatientLabsPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = await params;
    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Lab results</h2>
                    <Link className="text-link" href={`/provider/patients/${id}`}>
                        Patient overview
                    </Link>
                </div>
                <p className="muted">
                    Upload crystallography or 24-hour urine data. The workflow
                    can re-run to update treatment and prevention plans.
                </p>
            </div>

            <LabUploadPanel patientId={id} />
        </section>
    );
}
