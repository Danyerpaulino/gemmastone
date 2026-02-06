import Link from "next/link";

// Provider shell layout with quick navigation for the agentic workflow demo.

export const metadata = {
    title: "KidneyStone AI | Provider",
    description: "Provider workspace for KidneyStone AI workflows.",
};

const navLinks = [
    { href: "/dashboard", label: "Dashboard" },
    { href: "/patients", label: "Patients" },
    { href: "/upload", label: "CT Intake" },
    { href: "/", label: "Landing" },
];

export default function ProviderLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="shell">
            <aside className="sidebar">
                <div className="brand">
                    <span className="brand-mark">KS</span>
                    <div>
                        <p className="brand-title">KidneyStone AI</p>
                        <p className="brand-subtitle">Agentic workflow demo</p>
                    </div>
                </div>
                <nav className="nav">
                    {navLinks.map((link) => (
                        <Link key={link.href} href={link.href}>
                            {link.label}
                        </Link>
                    ))}
                </nav>
                <div className="sidebar-note">
                    <p className="eyebrow">Comms</p>
                    <p>
                        SMS + voice are mock only. Patient chat stays live to
                        showcase MedGemma responses.
                    </p>
                </div>
            </aside>
            <div className="shell-main">
                <header className="shell-header">
                    <div>
                        <p className="eyebrow">Provider workspace</p>
                        <h1>Clinical command center</h1>
                        <p className="lead">
                            Review AI findings, approve plans, and keep the
                            patient journey moving.
                        </p>
                    </div>
                    <div className="shell-actions">
                        <Link className="ghost-link" href="/upload">
                            Run CT intake
                        </Link>
                        <Link className="ghost-link" href="/patients">
                            View patients
                        </Link>
                    </div>
                </header>
                <div className="shell-content">{children}</div>
            </div>
        </div>
    );
}
