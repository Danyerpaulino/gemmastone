"use client";

import { useMemo } from "react";

import type { LabResultOut } from "@/lib/types";

const formatLabel = (value: string) => {
    try {
        return new Date(value).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
        });
    } catch (error) {
        return value;
    }
};

export default function LabTrendChart({
    labs,
    metricKey,
    label,
    unit,
}: {
    labs: LabResultOut[];
    metricKey: string;
    label: string;
    unit?: string;
}) {
    const points = useMemo(() => {
        const rows = labs
            .map((lab) => {
                const raw = lab.results?.[metricKey];
                const value = typeof raw === "number" ? raw : null;
                const date = lab.result_date || lab.created_at || "";
                return value !== null
                    ? { value, date: date || "", id: lab.id }
                    : null;
            })
            .filter(Boolean) as Array<{ value: number; date: string; id: string }>;

        const sorted = rows.sort((a, b) => a.date.localeCompare(b.date));
        const values = sorted.map((row) => row.value);
        const min = Math.min(...values, 0);
        const max = Math.max(...values, 1);
        const range = max - min || 1;

        const svgPoints = sorted.map((row, index) => {
            const x = (index / Math.max(sorted.length - 1, 1)) * 100;
            const y = 100 - ((row.value - min) / range) * 100;
            return { ...row, x, y };
        });

        return { svgPoints, min, max };
    }, [labs, metricKey]);

    if (!points.svgPoints.length) {
        return (
            <div className="chart empty">
                <div className="chart-header">
                    <div>
                        <p className="eyebrow">{label}</p>
                        <h3>No trend data</h3>
                    </div>
                </div>
                <p className="muted">Upload labs to see this trend.</p>
            </div>
        );
    }

    const polyline = points.svgPoints
        .map((point) => `${point.x},${point.y}`)
        .join(" ");

    return (
        <div className="chart">
            <div className="chart-header">
                <div>
                    <p className="eyebrow">{label}</p>
                    <h3>Trend</h3>
                </div>
                <span className="muted">
                    {Math.round(points.min)}–{Math.round(points.max)} {unit || ""}
                </span>
            </div>
            <svg viewBox="0 0 100 100" className="chart-line" aria-hidden="true">
                <polyline points={polyline} fill="none" />
                {points.svgPoints.map((point) => (
                    <circle key={point.id} cx={point.x} cy={point.y} r="1.8" />
                ))}
            </svg>
            <div className="chart-axis">
                <span>{formatLabel(points.svgPoints[0].date)}</span>
                <span>
                    {formatLabel(points.svgPoints[points.svgPoints.length - 1].date)}
                </span>
            </div>
        </div>
    );
}
