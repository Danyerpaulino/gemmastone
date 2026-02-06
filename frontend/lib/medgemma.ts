type MedgemmaSection = {
    text: string;
    kind: "heading" | "body";
};

const extractTextOutput = (value: unknown): string | null => {
    if (value == null) {
        return null;
    }
    if (typeof value === "string") {
        return value;
    }
    if (Array.isArray(value)) {
        for (const entry of value) {
            const extracted = extractTextOutput(entry);
            if (extracted !== null) {
                return extracted;
            }
        }
        return null;
    }
    if (typeof value === "object") {
        const obj = value as Record<string, unknown>;
        if (typeof obj.text === "string") {
            return obj.text;
        }
        if (typeof obj.raw_output === "string") {
            return obj.raw_output;
        }
        if (obj.result !== undefined) {
            const extracted = extractTextOutput(obj.result);
            if (extracted !== null) {
                return extracted;
            }
        }
        if (obj.output !== undefined) {
            const extracted = extractTextOutput(obj.output);
            if (extracted !== null) {
                return extracted;
            }
        }
        if (obj.predictions !== undefined) {
            const extracted = extractTextOutput(obj.predictions);
            if (extracted !== null) {
                return extracted;
            }
        }
    }
    return null;
};

export const normalizeMedgemmaText = (text: string): string => {
    const trimmed = text.trim();
    if (!trimmed) {
        return text;
    }
    if (!trimmed.startsWith("{") && !trimmed.startsWith("[")) {
        return text;
    }
    try {
        const parsed = JSON.parse(trimmed);
        const extracted = extractTextOutput(parsed);
        return extracted !== null ? extracted : text;
    } catch {
        return text;
    }
};

const stripMarkdown = (value: string): string => {
    let cleaned = value.replace(/\r\n/g, "\n");
    cleaned = cleaned.replace(/^\s*#{1,6}\s+/g, "");
    cleaned = cleaned.replace(/^\s*[-*]\s+/g, "");
    cleaned = cleaned.replace(/^\s*\d+\.\s+/g, "");
    cleaned = cleaned.replace(/\*\*(.*?)\*\*/g, "$1");
    cleaned = cleaned.replace(/__(.*?)__/g, "$1");
    cleaned = cleaned.replace(/`([^`]+)`/g, "$1");
    return cleaned.trim();
};

export const formatMedgemmaSections = (text: string): MedgemmaSection[] => {
    const normalized = normalizeMedgemmaText(text);
    const lines = normalized.replace(/\r\n/g, "\n").split("\n");
    const paragraphs: string[] = [];
    let buffer: string[] = [];

    const flush = () => {
        if (!buffer.length) {
            return;
        }
        const paragraph = buffer.join(" ").replace(/\s+/g, " ").trim();
        if (paragraph) {
            paragraphs.push(paragraph);
        }
        buffer = [];
    };

    for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) {
            flush();
            continue;
        }
        const cleaned = stripMarkdown(trimmed);
        if (cleaned) {
            buffer.push(cleaned);
        }
    }
    flush();

    return paragraphs.map((paragraph) => {
        const isHeading =
            paragraph.length <= 70 &&
            /[?!:]$/.test(paragraph);
        return {
            text: paragraph,
            kind: isHeading ? "heading" : "body",
        };
    });
};
