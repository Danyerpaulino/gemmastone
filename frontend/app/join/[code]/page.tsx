"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { API_TOKEN, API_URL } from "@/lib/api";
import OTPInput from "@/components/OTPInput";
import type {
    OnboardingResponse,
    OtpRequestResponse,
    OtpVerifyResponse,
    ProviderReferral,
} from "@/lib/types";

type Step = "form" | "otp" | "done";

const buildHeaders = () => ({
    "Content-Type": "application/json",
    ...(API_TOKEN ? { Authorization: `Bearer ${API_TOKEN}` } : {}),
});

export default function JoinPage({ params }: { params: { code: string } }) {
    const router = useRouter();
    const apiBase = useMemo(() => API_URL.replace(/\/$/, ""), []);
    const [provider, setProvider] = useState<ProviderReferral | null>(null);
    const [providerStatus, setProviderStatus] = useState<"loading" | "error" | "ready">("loading");
    const [providerError, setProviderError] = useState("");

    const [step, setStep] = useState<Step>("form");
    const [firstName, setFirstName] = useState("");
    const [lastName, setLastName] = useState("");
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [otp, setOtp] = useState("");
    const [status, setStatus] = useState("");
    const [statusType, setStatusType] = useState<"idle" | "error" | "success">("idle");
    const [debugCode, setDebugCode] = useState<string | null>(null);

    useEffect(() => {
        let isActive = true;
        const loadProvider = async () => {
            setProviderStatus("loading");
            setProviderError("");
            try {
                const response = await fetch(
                    `${apiBase}/onboarding/provider/${params.code}`,
                    {
                        headers: buildHeaders(),
                        cache: "no-store",
                    }
                );
                if (!response.ok) {
                    const payload = await response.json();
                    throw new Error(payload?.detail || "Invalid referral code.");
                }
                const payload = (await response.json()) as ProviderReferral;
                if (!isActive) {
                    return;
                }
                setProvider(payload);
                setProviderStatus("ready");
            } catch (error) {
                if (!isActive) {
                    return;
                }
                setProviderStatus("error");
                setProviderError(
                    error instanceof Error
                        ? error.message
                        : "Unable to load provider."
                );
            }
        };

        loadProvider();
        return () => {
            isActive = false;
        };
    }, [apiBase, params.code]);

    const setStatusMessage = (message: string, type: "idle" | "error" | "success" = "idle") => {
        setStatus(message);
        setStatusType(type);
    };

    const submitDetails = async () => {
        setStatusMessage("");
        setDebugCode(null);
        if (!firstName.trim() || !lastName.trim() || !phone.trim()) {
            setStatusMessage("Please enter your name and phone number.", "error");
            return;
        }

        try {
            setStatusMessage("Sending verification code...");
            const response = await fetch(`${apiBase}/onboarding/join/${params.code}`, {
                method: "POST",
                headers: buildHeaders(),
                body: JSON.stringify({
                    first_name: firstName.trim(),
                    last_name: lastName.trim(),
                    phone: phone.trim(),
                    email: email.trim() || null,
                }),
            });
            const payload = (await response.json()) as
                | OnboardingResponse
                | { detail?: string };
            if (!response.ok) {
                throw new Error(
                    (payload as { detail?: string }).detail ||
                        "Unable to start onboarding."
                );
            }
            const success = payload as OnboardingResponse;
            setPhone(success.phone || phone);
            setDebugCode(success.debug_code || null);
            setStep("otp");
            setStatusMessage("Code sent. Enter it below.", "success");
        } catch (error) {
            setStatusMessage(
                error instanceof Error ? error.message : "Unable to start onboarding.",
                "error"
            );
        }
    };

    const verifyCode = async () => {
        setStatusMessage("");
        if (!otp.trim()) {
            setStatusMessage("Enter the 6-digit code we sent you.", "error");
            return;
        }
        try {
            setStatusMessage("Verifying...");
            const response = await fetch(`${apiBase}/auth/verify-otp`, {
                method: "POST",
                headers: buildHeaders(),
                credentials: "include",
                body: JSON.stringify({
                    phone: phone.trim(),
                    code: otp.trim(),
                }),
            });
            const payload = (await response.json()) as
                | OtpVerifyResponse
                | { detail?: string };
            if (!response.ok) {
                throw new Error(
                    (payload as { detail?: string }).detail ||
                        "Verification failed."
                );
            }
            setStep("done");
            setStatusMessage("You're all set! Redirecting...", "success");
            setTimeout(() => {
                router.push("/dashboard");
            }, 1200);
        } catch (error) {
            setStatusMessage(
                error instanceof Error ? error.message : "Verification failed.",
                "error"
            );
        }
    };

    const resendCode = async () => {
        setStatusMessage("");
        if (!phone.trim()) {
            return;
        }
        try {
            setStatusMessage("Resending code...");
            const response = await fetch(`${apiBase}/auth/request-otp`, {
                method: "POST",
                headers: buildHeaders(),
                body: JSON.stringify({ phone: phone.trim() }),
            });
            const payload = (await response.json()) as
                | OtpRequestResponse
                | { detail?: string };
            if (!response.ok) {
                throw new Error(
                    (payload as { detail?: string }).detail ||
                        "Unable to resend code."
                );
            }
            const success = payload as OtpRequestResponse;
            setDebugCode(success.debug_code || null);
            setStatusMessage("New code sent.", "success");
        } catch (error) {
            setStatusMessage(
                error instanceof Error ? error.message : "Unable to resend code.",
                "error"
            );
        }
    };

    const providerName = provider?.name || "Your provider";

    return (
        <section className="page auth-wrapper">
            <div className="card auth-card">
                {providerStatus === "loading" ? (
                    <p className="status">Loading your referral...</p>
                ) : null}
                {providerStatus === "error" ? (
                    <>
                        <h2>We couldn't find that link.</h2>
                        <p className="muted">
                            {providerError ||
                                "Ask your provider for a valid QR code."}
                        </p>
                    </>
                ) : null}
                {providerStatus === "ready" ? (
                    <>
                        <p className="eyebrow">Welcome</p>
                        <h1>{providerName} invited you</h1>
                        {provider?.practice_name ? (
                            <p className="lead">{provider.practice_name}</p>
                        ) : (
                            <p className="lead">
                                Set up your prevention assistant in under a
                                minute.
                            </p>
                        )}

                        {step === "form" ? (
                            <div className="auth-form">
                                <div className="form-grid single">
                                    <label>
                                        First name
                                        <input
                                            value={firstName}
                                            onChange={(event) =>
                                                setFirstName(event.target.value)
                                            }
                                            placeholder="Jane"
                                        />
                                    </label>
                                    <label>
                                        Last name
                                        <input
                                            value={lastName}
                                            onChange={(event) =>
                                                setLastName(event.target.value)
                                            }
                                            placeholder="Doe"
                                        />
                                    </label>
                                    <label>
                                        Phone number
                                        <input
                                            type="tel"
                                            value={phone}
                                            onChange={(event) =>
                                                setPhone(event.target.value)
                                            }
                                            placeholder="(555) 123-4567"
                                        />
                                    </label>
                                    <label>
                                        Email (optional)
                                        <input
                                            type="email"
                                            value={email}
                                            onChange={(event) =>
                                                setEmail(event.target.value)
                                            }
                                            placeholder="jane@example.com"
                                        />
                                    </label>
                                </div>
                                <div className="actions">
                                    <button type="button" onClick={submitDetails}>
                                        Get started
                                    </button>
                                    {status ? (
                                        <p
                                            className={`status ${
                                                statusType === "error"
                                                    ? "error"
                                                    : statusType === "success"
                                                    ? "success"
                                                    : ""
                                            }`}
                                        >
                                            {status}
                                        </p>
                                    ) : null}
                                </div>
                            </div>
                        ) : null}

                        {step === "otp" ? (
                            <div className="auth-form">
                                <div className="form-grid single">
                                    <label>
                                        Enter your 6-digit code
                                        <OTPInput value={otp} onChange={setOtp} />
                                    </label>
                                </div>
                                <div className="actions">
                                    <button type="button" onClick={verifyCode}>
                                        Verify
                                    </button>
                                    <button
                                        type="button"
                                        className="ghost"
                                        onClick={resendCode}
                                    >
                                        Resend code
                                    </button>
                                </div>
                                {debugCode ? (
                                    <p className="status">
                                        Dev mode code: {debugCode}
                                    </p>
                                ) : null}
                                {status ? (
                                    <p
                                        className={`status ${
                                            statusType === "error"
                                                ? "error"
                                                : statusType === "success"
                                                ? "success"
                                                : ""
                                        }`}
                                    >
                                        {status}
                                    </p>
                                ) : null}
                            </div>
                        ) : null}

                        {step === "done" ? (
                            <div className="auth-form">
                                <p className="lead">
                                    You're verified. We'll call you shortly to
                                    start your intake.
                                </p>
                            </div>
                        ) : null}
                    </>
                ) : null}
            </div>
        </section>
    );
}
