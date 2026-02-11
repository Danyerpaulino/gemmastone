import PatientShell from "@/components/PatientShell";

export const metadata = {
    title: "StoneXero | Patient",
    description: "Patient prevention companion for StoneXero.",
};

export default function PatientLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <PatientShell>{children}</PatientShell>;
}
