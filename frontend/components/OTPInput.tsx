"use client";

import { useMemo, useRef } from "react";

const clampValue = (value: string, length: number) =>
    value.replace(/\D/g, "").slice(0, length);

export default function OTPInput({
    value,
    onChange,
    length = 6,
    disabled = false,
    autoFocus = false,
}: {
    value: string;
    onChange: (value: string) => void;
    length?: number;
    disabled?: boolean;
    autoFocus?: boolean;
}) {
    const inputsRef = useRef<Array<HTMLInputElement | null>>([]);
    const digits = useMemo(() => {
        const sanitized = clampValue(value, length);
        return Array.from({ length }, (_, index) => sanitized[index] || "");
    }, [value, length]);

    const focusIndex = (index: number) => {
        const target = inputsRef.current[index];
        if (target) {
            target.focus();
            target.select();
        }
    };

    const updateAt = (index: number, nextValue: string) => {
        const current = clampValue(value, length).split("");
        current[index] = nextValue;
        onChange(current.join("").slice(0, length));
    };

    const handleInput = (index: number, next: string) => {
        const cleaned = next.replace(/\D/g, "");
        if (!cleaned) {
            updateAt(index, "");
            return;
        }
        const current = clampValue(value, length).split("");
        let cursor = index;
        for (const digit of cleaned) {
            if (cursor >= length) {
                break;
            }
            current[cursor] = digit;
            cursor += 1;
        }
        onChange(current.join("").slice(0, length));
        focusIndex(Math.min(cursor, length - 1));
    };

    return (
        <div className="otp-input" aria-label="One time passcode">
            {digits.map((digit, index) => (
                <input
                    key={`otp-${index}`}
                    ref={(node) => {
                        inputsRef.current[index] = node;
                    }}
                    type="text"
                    inputMode="numeric"
                    autoComplete={index === 0 ? "one-time-code" : "off"}
                    pattern="[0-9]*"
                    maxLength={length}
                    value={digit}
                    onChange={(event) => handleInput(index, event.target.value)}
                    onKeyDown={(event) => {
                        if (event.key === "Backspace" && !digit && index > 0) {
                            focusIndex(index - 1);
                        }
                        if (event.key === "ArrowLeft" && index > 0) {
                            event.preventDefault();
                            focusIndex(index - 1);
                        }
                        if (event.key === "ArrowRight" && index < length - 1) {
                            event.preventDefault();
                            focusIndex(index + 1);
                        }
                    }}
                    onPaste={(event) => {
                        event.preventDefault();
                        const text = event.clipboardData.getData("text");
                        handleInput(index, text);
                    }}
                    disabled={disabled}
                    autoFocus={autoFocus && index === 0}
                />
            ))}
        </div>
    );
}
