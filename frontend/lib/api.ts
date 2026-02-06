export const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080/api";
export const API_TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";

export type ApiResult<T> = {
    data?: T;
    error?: string;
    status?: number;
};

const normalizeBase = (value: string) => value.replace(/\/$/, "");

const buildAuthHeaders = (): Record<string, string> => {
    if (!API_TOKEN) {
        return {};
    }
    return { Authorization: `Bearer ${API_TOKEN}` };
};

const toUrl = (path: string) => {
    if (path.startsWith("http")) {
        return path;
    }
    const base = normalizeBase(API_URL);
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${base}${normalized}`;
};

export async function fetchJson<T>(
    path: string,
    options: RequestInit = {}
): Promise<ApiResult<T>> {
    const url = toUrl(path);
    const headers = {
        ...buildAuthHeaders(),
        ...(options.headers || {}),
    } as Record<string, string>;

    try {
        const response = await fetch(url, {
            ...options,
            headers,
            cache: "no-store",
        });
        const text = await response.text();
        const payload = text ? (JSON.parse(text) as T) : undefined;
        if (!response.ok) {
            return {
                error:
                    (payload as { detail?: string } | undefined)?.detail ||
                    response.statusText,
                status: response.status,
            };
        }
        return { data: payload, status: response.status };
    } catch (error) {
        return {
            error:
                error instanceof Error
                    ? error.message
                    : "Unable to reach API",
        };
    }
}
