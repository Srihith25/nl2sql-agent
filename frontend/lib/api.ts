import type { ConnectResponse, QueryResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Turn a failed fetch Response into a clean Error message for display.
 * FastAPI errors arrive as `{"detail": "..."}` — surface just that string
 * instead of dumping the raw status code + JSON envelope on the page.
 */
async function apiError(res: Response, fallback: string): Promise<Error> {
  const text = await res.text().catch(() => "");
  let detail = text;
  try {
    const parsed = JSON.parse(text);
    if (typeof parsed?.detail === "string" && parsed.detail.trim()) detail = parsed.detail;
  } catch {
    // Response wasn't JSON (e.g. a proxy error page) — fall through to raw text.
  }
  detail = detail?.trim() || res.statusText || fallback;
  return new Error(detail);
}

export async function ask(question: string, session_id?: string, verify?: boolean): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: session_id ?? null, verify: verify ?? false }),
  });
  if (!res.ok) throw await apiError(res, "Something went wrong answering that question.");
  return res.json();
}

export async function connectUrl(db_url: string, label?: string): Promise<ConnectResponse> {
  const res = await fetch(`${API_URL}/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_url, label: label ?? "" }),
  });
  if (!res.ok) throw await apiError(res, "Couldn't connect to that database.");
  return res.json();
}

export async function uploadFile(file: File): Promise<ConnectResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) throw await apiError(res, "Couldn't upload that file.");
  return res.json();
}
