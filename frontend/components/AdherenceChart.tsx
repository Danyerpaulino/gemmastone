"use client";

import { useMemo } from "react";

import type { ComplianceLogOut } from "@/lib/types";

const toDateKey = (value: string) => value.split("T")[0];

const formatLabel = (value: Date) =>
    value.toLocaleDateString(undefined, { month: "short", day: "numeric" });

export default function AdherenceChart({
    logs,
    days = 14,
}: {
    logs: ComplianceLogOut[];
    days?: number;
}) {
    const data = useMemo(() => {
        const logMap = new Map<string, ComplianceLogOut>();
        logs.forEach((log) => {
            logMap.set(toDateKey(log.log_date), log);
        });

        const today = new Date();
        const entries = Array.from({ length: days }, (_, index) => {
            const date = new Date(today);
            date.setDate(today.getDate() - (days - 1 - index));
            const key = date.toISOString().split("T")[0];
            const log = logMap.get(key);
            const hydration = log?.fluid_intake_ml ? 1 : 0;
            const meds = log?.medication_taken ? 1 : 0;
            const diet =
                typeof log?.dietary_compliance_score === "number"
                    ? Math.max(0, Math.min(1, log.dietary_compliance_score))
                    : 0;
            const score = (hydration + meds + diet) / 3;
            return {
                key,
                label: formatLabel(date),
                score,
                hydration,
                meds,
                diet,
            };
        });
        return entries;
    }, [logs, days]);

    return (
        <div className="chart">
            <div className="chart-header">
                <div>
                    <p className="eyebrow">Adherence</p>
                    <h3>Last {days} days</h3>
                </div>
                <span className="muted">Hydration · Meds · Diet</span>
            </div>
            <div className="chart-bars">
                {data.map((item) => (
                    <div key={item.key} className="chart-bar" aria-label={item.label}>
                        <span style={{ height: `${Math.round(item.score * 100)}%` }} />
                    </div>
                ))}
            </div>
            <div className="chart-axis">
                <span>{data[0]?.label}</span>
                <span>{data[data.length - 1]?.label}</span>
            </div>
        </div>
    );
}
