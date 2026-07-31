import type { ConnectResponse, QueryResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function ask(question: string, session_id?: string, verify?: boolean): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, session_id: session_id ?? null, verify: verify ?? false }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function connectUrl(db_url: string, label?: string): Promise<ConnectResponse> {
  const res = await fetch(`${API_URL}/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ db_url, label: label ?? "" }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Connect failed: ${text}`);
  }
  return res.json();
}

export async function uploadFile(file: File): Promise<ConnectResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_URL}/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json();
}
