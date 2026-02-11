"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { API_URL } from "@/lib/api";
import type { OtpRequestResponse, OtpVerifyResponse } from "@/lib/types";

export type AuthSession = {
    patientId: string;
    providerId?: string | null;
    expiresAt?: string | null;
};

const SESSION_KEY = "kidneystone_session_v1";

const normalizeBase = (value: string) => value.replace(/\/$/, "");

const buildUrl = (path: string) => {
    if (path.startsWith("http")) {
        return path;
    }
    const base = normalizeBase(API_URL);
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${base}${normalized}`;
};

const parseSession = (payload: OtpVerifyResponse): AuthSession => ({
    patientId: payload.patient_id,
    providerId: payload.provider_id ?? null,
    expiresAt: payload.expires_at ?? null,
});

export const loadStoredSession = (): AuthSession | null => {
    if (typeof window === "undefined") {
        return null;
    }
    try {
        const raw = window.localStorage.getItem(SESSION_KEY);
        if (!raw) {
            return null;
        }
        const parsed = JSON.parse(raw) as AuthSession;
        if (!parsed?.patientId) {
            return null;
        }
        return parsed;
    } catch (error) {
        return null;
    }
};

export const saveSession = (session: AuthSession) => {
    if (typeof window === "undefined") {
        return;
    }
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
};

export const clearSession = () => {
    if (typeof window === "undefined") {
        return;
    }
    window.localStorage.removeItem(SESSION_KEY);
};

export async function requestOtp(phone: string): Promise<OtpRequestResponse> {
    const response = await fetch(buildUrl("/auth/request-otp"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone }),
    });
    const payload = (await response.json()) as OtpRequestResponse | { detail?: string };
    if (!response.ok) {
        throw new Error((payload as { detail?: string }).detail || "Unable to send OTP.");
    }
    return payload as OtpRequestResponse;
}

export async function verifyOtp(
    phone: string,
    code: string
): Promise<AuthSession> {
    const response = await fetch(buildUrl("/auth/verify-otp"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ phone, code }),
    });
    const payload = (await response.json()) as OtpVerifyResponse | { detail?: string };
    if (!response.ok) {
        throw new Error((payload as { detail?: string }).detail || "Verification failed.");
    }
    const session = parseSession(payload as OtpVerifyResponse);
    saveSession(session);
    return session;
}

export async function refreshSession(): Promise<AuthSession | null> {
    const response = await fetch(buildUrl("/auth/refresh"), {
        method: "POST",
        credentials: "include",
    });
    if (!response.ok) {
        return null;
    }
    const payload = (await response.json()) as OtpVerifyResponse;
    const session = parseSession(payload);
    saveSession(session);
    return session;
}

export async function logoutSession(): Promise<void> {
    try {
        await fetch(buildUrl("/auth/logout"), {
            method: "POST",
            credentials: "include",
        });
    } finally {
        clearSession();
    }
}

export function useAuthSession({
    required = false,
    redirectTo = "/login",
}: {
    required?: boolean;
    redirectTo?: string;
} = {}) {
    const router = useRouter();
    const [session, setSession] = useState<AuthSession | null>(null);
    const [status, setStatus] = useState<"loading" | "ready" | "unauth">("loading");

    const hydrate = useCallback(async () => {
        setStatus("loading");
        const stored = loadStoredSession();
        if (stored) {
            setSession(stored);
        }
        const refreshed = await refreshSession();
        if (refreshed) {
            setSession(refreshed);
            setStatus("ready");
            return refreshed;
        }
        if (stored) {
            setStatus("ready");
            return stored;
        }
        setSession(null);
        setStatus("unauth");
        return null;
    }, []);

    useEffect(() => {
        let active = true;
        hydrate().then((current) => {
            if (!active) {
                return;
            }
            if (!current && required) {
                router.replace(redirectTo);
            }
        });
        return () => {
            active = false;
        };
    }, [hydrate, required, redirectTo, router]);

    const refresh = useCallback(async () => {
        const current = await refreshSession();
        if (current) {
            setSession(current);
            setStatus("ready");
            return current;
        }
        setSession(null);
        setStatus("unauth");
        return null;
    }, []);

    return { session, status, refresh };
}
