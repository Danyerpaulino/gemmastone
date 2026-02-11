import PatientShell from "@/components/PatientShell";

export const metadata = {
    title: "KidneyStones AI | Patient",
    description: "Patient prevention companion for KidneyStones AI.",
};

export default function PatientLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <PatientShell>{children}</PatientShell>;
}
