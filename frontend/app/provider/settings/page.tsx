import { fetchJson } from "@/lib/api";
import QRCodeDisplay from "@/components/QRCodeDisplay";
import type { ProviderList } from "@/lib/types";

export default async function ProviderSettingsPage() {
    const providers = await fetchJson<ProviderList>("/providers/?limit=50");

    return (
        <section className="stack">
            <div className="card">
                <div className="card-header">
                    <h2>Provider QR codes</h2>
                    <span className="badge">Live</span>
                </div>
                <p className="muted">
                    Print or share these QR codes to onboard patients instantly.
                    Each code links directly to the phone-first signup flow.
                </p>
            </div>

            {providers.data?.items?.length ? (
                <div className="grid">
                    {providers.data.items.map((provider) => (
                        <QRCodeDisplay
                            key={provider.id}
                            providerName={provider.name}
                            referralCode={provider.referral_code}
                            qrCodeUrl={provider.qr_code_url}
                        />
                    ))}
                </div>
            ) : (
                <div className="card">
                    <p className="empty">
                        {providers.error
                            ? `Unable to load providers: ${providers.error}`
                            : "No providers found yet."}
                    </p>
                </div>
            )}
        </section>
    );
}
