"use client";

import { useMemo, useState } from "react";

const resolveJoinUrl = (referralCode?: string | null) => {
    if (!referralCode) {
        return "";
    }
    if (typeof window !== "undefined") {
        return `${window.location.origin}/join/${referralCode}`;
    }
    return `/join/${referralCode}`;
};

export default function QRCodeDisplay({
    providerName,
    referralCode,
    qrCodeUrl,
}: {
    providerName?: string | null;
    referralCode?: string | null;
    qrCodeUrl?: string | null;
}) {
    const [copied, setCopied] = useState(false);
    const joinUrl = useMemo(() => resolveJoinUrl(referralCode), [referralCode]);

    const handleCopy = async () => {
        if (!joinUrl) {
            return;
        }
        try {
            await navigator.clipboard.writeText(joinUrl);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 2000);
        } catch (error) {
            setCopied(false);
        }
    };

    return (
        <div className="card qr-card">
            <div className="card-header">
                <div>
                    <p className="eyebrow">Referral QR</p>
                    <h3>{providerName || "Provider"}</h3>
                </div>
                <span className="badge">Live</span>
            </div>
            <div className="qr-content">
                <div className="qr-frame">
                    {qrCodeUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={qrCodeUrl} alt="Provider referral QR" />
                    ) : (
                        <div className="qr-placeholder">
                            <span>No QR uploaded</span>
                        </div>
                    )}
                </div>
                <div className="qr-meta">
                    <p className="muted">Referral code</p>
                    <p className="qr-code">{referralCode || "—"}</p>
                    <p className="muted">Join link</p>
                    <p className="qr-link">{joinUrl || "—"}</p>
                    <div className="actions">
                        <button type="button" onClick={handleCopy} disabled={!joinUrl}>
                            {copied ? "Copied" : "Copy link"}
                        </button>
                        {qrCodeUrl ? (
                            <a className="ghost-link" href={qrCodeUrl} download>
                                Download QR
                            </a>
                        ) : null}
                    </div>
                </div>
            </div>
        </div>
    );
}
