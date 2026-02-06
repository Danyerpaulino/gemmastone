import Link from "next/link";

// Patient shell layout emphasizing the chat-first engagement experience.

export const metadata = {
    title: "KidneyStone AI | Patient",
    description: "Patient engagement demo for KidneyStone AI.",
};

const navLinks = [
    { href: "/chat", label: "Chat" },
    { href: "/my-plan", label: "My plan" },
    { href: "/progress", label: "Progress" },
    { href: "/", label: "Landing" },
];

export default function PatientLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="shell patient-shell">
            <aside className="sidebar patient-sidebar">
                <div className="brand">
                    <span className="brand-mark">KS</span>
                    <div>
                        <p className="brand-title">KidneyStone AI</p>
                        <p className="brand-subtitle">Patient companion</p>
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
                    <p className="eyebrow">Experience</p>
                    <p>
                        Chat is live with MedGemma. Everything else is mocked
                        for demo safety.
                    </p>
                </div>
            </aside>
            <div className="shell-main">
                <header className="shell-header">
                    <div>
                        <p className="eyebrow">Patient experience</p>
                        <h1>Your support plan</h1>
                        <p className="lead">
                            Stay hydrated, track progress, and ask questions at
                            any time.
                        </p>
                    </div>
                    <div className="shell-actions">
                        <Link className="ghost-link" href="/chat">
                            Open chat
                        </Link>
                        <Link className="ghost-link" href="/my-plan">
                            View plan
                        </Link>
                    </div>
                </header>
                <div className="shell-content">{children}</div>
            </div>
        </div>
    );
}
