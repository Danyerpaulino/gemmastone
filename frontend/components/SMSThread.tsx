"use client";

import type { SmsMessageOut } from "@/lib/types";

const formatTime = (value?: string | null) => {
    if (!value) {
        return "";
    }
    try {
        return new Date(value).toLocaleString();
    } catch (error) {
        return value;
    }
};

export default function SMSThread({ messages }: { messages: SmsMessageOut[] }) {
    if (!messages.length) {
        return <p className="empty">No SMS history yet.</p>;
    }

    const ordered = [...messages].sort((a, b) =>
        (a.created_at || "").localeCompare(b.created_at || "")
    );

    return (
        <div className="thread">
            {ordered.map((message) => (
                <div
                    key={message.id}
                    className={`thread-bubble ${message.direction === "outbound" ? "outbound" : "inbound"}`}
                >
                    <p>{message.content || "(no content)"}</p>
                    <span>
                        {formatTime(message.created_at)}
                        {message.status ? ` • ${message.status}` : ""}
                    </span>
                </div>
            ))}
        </div>
    );
}
