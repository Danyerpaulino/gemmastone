"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import OTPInput from "@/components/OTPInput";
import { requestOtp, verifyOtp } from "@/lib/auth";

export default function LoginPage() {
    const router = useRouter();
    const [step, setStep] = useState<"request" | "verify">("request");
    const [phone, setPhone] = useState("");
    const [code, setCode] = useState("");
    const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
    const [message, setMessage] = useState("");
    const [debugCode, setDebugCode] = useState<string | null>(null);

    const handleRequest = async () => {
        if (!phone.trim()) {
            setStatus("error");
            setMessage("Enter the phone number you used for signup.");
            return;
        }
        setStatus("loading");
        setMessage("");
        try {
            const response = await requestOtp(phone.trim());
            setDebugCode(response.debug_code || null);
            setStep("verify");
            setStatus("idle");
            setMessage("We sent a code to your phone.");
        } catch (error) {
            setStatus("error");
            setMessage(error instanceof Error ? error.message : "Unable to send code.");
        }
    };

    const handleVerify = async () => {
        if (!code.trim()) {
            setStatus("error");
            setMessage("Enter the 6-digit code.");
            return;
        }
        setStatus("loading");
        setMessage("");
        try {
            await verifyOtp(phone.trim(), code.trim());
            router.push("/dashboard");
        } catch (error) {
            setStatus("error");
            setMessage(error instanceof Error ? error.message : "Verification failed.");
        }
    };

    return (
        <main className="page auth-wrapper">
            <section className="card auth-card">
                <p className="eyebrow">Patient login</p>
                <h1>Verify your phone</h1>
                <p className="lead">
                    Enter the mobile number you used when you scanned your
                    provider's QR code.
                </p>

                {step === "request" ? (
                    <div className="auth-form">
                        <label>
                            Phone number
                            <input
                                type="tel"
                                value={phone}
                                onChange={(event) => setPhone(event.target.value)}
                                placeholder="(555) 123-4567"
                            />
                        </label>
                        <div className="actions">
                            <button type="button" onClick={handleRequest} disabled={status === "loading"}>
                                {status === "loading" ? "Sending..." : "Send code"}
                            </button>
                            <p className={`status ${status === "error" ? "error" : ""}`}>
                                {message}
                            </p>
                        </div>
                    </div>
                ) : null}

                {step === "verify" ? (
                    <div className="auth-form">
                        <label>Enter the 6-digit code</label>
                        <OTPInput value={code} onChange={setCode} autoFocus />
                        <div className="actions">
                            <button type="button" onClick={handleVerify} disabled={status === "loading"}>
                                {status === "loading" ? "Verifying..." : "Verify"}
                            </button>
                            <button
                                type="button"
                                className="ghost"
                                onClick={handleRequest}
                                disabled={status === "loading"}
                            >
                                Resend
                            </button>
                        </div>
                        {debugCode ? (
                            <p className="status">Dev mode code: {debugCode}</p>
                        ) : null}
                        <p className={`status ${status === "error" ? "error" : ""}`}>
                            {message}
                        </p>
                    </div>
                ) : null}
            </section>
        </main>
    );
}
