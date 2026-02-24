import PatientShell from "@/components/PatientShell";

export const metadata = {
    title: "GemmaStone | Patient",
    description: "Patient prevention companion for GemmaStone.",
};

export default function PatientLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <PatientShell>{children}</PatientShell>;
}
