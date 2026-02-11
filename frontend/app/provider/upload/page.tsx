import CTIntake from "@/components/CTIntake";

export default function UploadPage() {
    return (
        <section className="stack">
            <CTIntake
                eyebrow="CT Intake"
                title="Run CT analysis"
                subtitle="Upload imaging, attach labs, and generate the full agentic workflow output."
                hideHero
            />
        </section>
    );
}
