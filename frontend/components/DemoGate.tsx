"use client";

import {
    createContext,
    useCallback,
    useContext,
    useEffect,
    useMemo,
    useState,
} from "react";

const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "";
const ACCESS_KEY = "kidneystone_demo_access_v1";

type DemoGateContextValue = {
    isUnlocked: boolean;
    requiresGate: boolean;
    lock: () => void;
};

const DemoGateContext = createContext<DemoGateContextValue | null>(null);

export const useDemoGate = () => {
    const context = useContext(DemoGateContext);
    if (context) {
        return context;
    }
    return {
        isUnlocked: !DEMO_PASSWORD,
        requiresGate: Boolean(DEMO_PASSWORD),
        lock: () => {},
    };
};

export default function DemoGate({
    children,
}: {
    children: React.ReactNode;
}) {
    const requiresGate = Boolean(DEMO_PASSWORD);
    const accessToken = DEMO_PASSWORD ? `v1:${btoa(DEMO_PASSWORD)}` : "";
    const [isUnlocked, setIsUnlocked] = useState(!requiresGate);
    const [accessInput, setAccessInput] = useState("");
    const [accessError, setAccessError] = useState("");

    useEffect(() => {
        if (!requiresGate) {
            setIsUnlocked(true);
            return;
        }
        const saved = window.localStorage.getItem(ACCESS_KEY);
        if (saved === accessToken) {
            setIsUnlocked(true);
        }
    }, [requiresGate, accessToken]);

    const lock = useCallback(() => {
        if (typeof window !== "undefined") {
            window.localStorage.removeItem(ACCESS_KEY);
        }
        setIsUnlocked(false);
        setAccessInput("");
        setAccessError("");
    }, []);

    const handleUnlock = (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        if (!requiresGate) {
            setIsUnlocked(true);
            return;
        }
        if (accessInput.trim() === DEMO_PASSWORD) {
            window.localStorage.setItem(ACCESS_KEY, accessToken);
            setIsUnlocked(true);
            setAccessError("");
        } else {
            setAccessError("Incorrect access code. Try again.");
        }
    };

    const contextValue = useMemo(
        () => ({
            isUnlocked,
            requiresGate,
            lock,
        }),
        [isUnlocked, requiresGate, lock]
    );

    return (
        <DemoGateContext.Provider value={contextValue}>
            {requiresGate && !isUnlocked ? (
                <main className="page auth-wrapper">
                    <section className="card auth-card">
                        <p className="eyebrow">Demo access</p>
                        <h1>Enter the shared access code</h1>
                        <p className="lead">
                            This demo is gated for the review team. Ask the
                            project owner for the access code.
                        </p>
                        <form className="auth-form" onSubmit={handleUnlock}>
                            <label>
                                Access code
                                <input
                                    type="password"
                                    value={accessInput}
                                    onChange={(event) =>
                                        setAccessInput(event.target.value)
                                    }
                                    placeholder="Shared demo code"
                                    required
                                />
                            </label>
                            <div className="actions auth-actions">
                                <button type="submit">Unlock</button>
                                <p className="status error">
                                    {accessError || " "}
                                </p>
                            </div>
                        </form>
                    </section>
                </main>
            ) : (
                children
            )}
        </DemoGateContext.Provider>
    );
}
