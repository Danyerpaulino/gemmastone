import Link from "next/link";

export const metadata = {
    title: "StoneXero | Provider",
    description: "Provider workspace for StoneXero compliance workflows.",
};

const navLinks = [
    { href: "/provider/dashboard", label: "Dashboard" },
    { href: "/provider/patients", label: "Patients" },
    { href: "/provider/upload", label: "CT Intake" },
    { href: "/provider/settings", label: "QR Codes" },
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
                    <span className="brand-mark">SX</span>
                    <div>
                        <p className="brand-title">StoneXero</p>
                        <p className="brand-subtitle">Compliance center</p>
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
                    <p className="eyebrow">Engagement</p>
                    <p>
                        SMS + voice are live. Calls and messages are logged for
                        compliance review.
                    </p>
                </div>
            </aside>
            <div className="shell-main">
                <header className="shell-header">
                    <div>
                        <p className="eyebrow">Provider workspace</p>
                        <h1>Compliance command center</h1>
                        <p className="lead">
                            Review engagement data, approve plans, and keep the
                            patient journey on track.
                        </p>
                    </div>
                    <div className="shell-actions">
                        <Link className="ghost-link" href="/provider/settings">
                            QR codes
                        </Link>
                        <Link className="ghost-link" href="/provider/patients">
                            Patient list
                        </Link>
                    </div>
                </header>
                <div className="shell-content">{children}</div>
            </div>
        </div>
    );
}
