"use client";
import { useRef, useState } from "react";
import { connectUrl, uploadFile } from "@/lib/api";
import type { ActiveSession } from "@/lib/types";
import { Database, FileText, Upload, ArrowRight, Loader2 } from "lucide-react";

interface Props {
  onConnect: (session: ActiveSession) => void;
  onDemo: () => void;
}

const DB_TYPES = [
  { label: "PostgreSQL", placeholder: "postgresql://user:password@host:5432/dbname" },
  { label: "MySQL",      placeholder: "mysql+pymysql://user:password@host:3306/dbname" },
  { label: "SQLite",     placeholder: "sqlite:///path/to/file.db" },
  { label: "DuckDB",     placeholder: "duckdb:///path/to/file.duckdb" },
];

type Tab = "url" | "file";

export default function ConnectModal({ onConnect, onDemo }: Props) {
  const [tab, setTab]           = useState<Tab>("url");
  const [urlValue, setUrlValue] = useState("");
  const [label, setLabel]       = useState("");
  const [file, setFile]         = useState<File | null>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleConnect() {
    setError(null);
    setLoading(true);
    try {
      let resp;
      if (tab === "url") {
        if (!urlValue.trim()) { setError("Enter a connection string."); return; }
        resp = await connectUrl(urlValue.trim(), label.trim());
      } else {
        if (!file) { setError("Select a file."); return; }
        resp = await uploadFile(file);
      }
      onConnect({ session_id: resp.session_id, label: resp.label, tables: resp.tables });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4"
         style={{ background: "rgba(0,0,0,0.5)", backdropFilter: "blur(8px)" }}>
      <div
        className="w-full max-w-md animate-fade-in"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "1.25rem",
          boxShadow: "var(--shadow-lg)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div className="px-6 pt-6 pb-4 flex items-center gap-3" style={{ borderBottom: "1px solid var(--border)" }}>
          <span className="logo-mark">
            <Database size={15} strokeWidth={2.25} />
          </span>
          <div>
            <h2 className="text-base font-semibold text-fg">Connect a database</h2>
            <p className="text-xs text-muted mt-0.5">
              PostgreSQL · MySQL · SQLite · DuckDB · CSV · Parquet
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: "1px solid var(--border)" }}>
          {(["url", "file"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className="flex-1 py-2.5 text-xs font-medium transition-colors"
              style={{
                color: tab === t ? "var(--accent)" : "var(--fg-muted)",
                borderBottom: tab === t ? "2px solid var(--accent)" : "2px solid transparent",
              }}
            >
              {t === "url" ? "Connection String" : "Upload File"}
            </button>
          ))}
        </div>

        <div className="px-6 py-5 space-y-4">
          {tab === "url" ? (
            <>
              <div>
                <label className="text-xs font-medium text-muted block mb-1.5">Connection string</label>
                <input
                  className="input-base font-code"
                  type="text"
                  value={urlValue}
                  onChange={(e) => setUrlValue(e.target.value)}
                  placeholder={DB_TYPES[0].placeholder}
                  onKeyDown={(e) => e.key === "Enter" && handleConnect()}
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted block mb-1.5">Label (optional)</label>
                <input
                  className="input-base"
                  type="text"
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  placeholder="My production DB"
                />
              </div>
              <div className="flex flex-wrap gap-1.5">
                {DB_TYPES.map((d) => (
                  <button
                    key={d.label}
                    onClick={() => setUrlValue(d.placeholder)}
                    className="text-xs px-2.5 py-1 rounded-lg transition-all"
                    style={{
                      background: "var(--surface-2)",
                      border: "1px solid var(--border)",
                      color: "var(--fg-2)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--accent)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--accent)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.borderColor = "var(--border)";
                      (e.currentTarget as HTMLButtonElement).style.color = "var(--fg-2)";
                    }}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div
              onClick={() => fileRef.current?.click()}
              className="rounded-xl p-8 text-center cursor-pointer transition-all"
              style={{
                border: "2px dashed var(--border)",
                background: file ? "var(--accent-bg)" : "transparent",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--accent)")}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--border)")}
            >
              <div className="flex items-center justify-center mb-2" style={{ color: file ? "var(--accent)" : "var(--fg-muted)" }}>
                {file ? <FileText size={26} strokeWidth={1.75} /> : <Upload size={26} strokeWidth={1.75} />}
              </div>
              <p className="text-sm text-fg-2 font-medium">
                {file ? file.name : "Click to select a file"}
              </p>
              <p className="text-xs text-muted mt-1">.csv · .db · .sqlite · .duckdb · .parquet</p>
              <input
                ref={fileRef}
                type="file"
                accept=".csv,.db,.sqlite,.duckdb,.parquet"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </div>
          )}

          {error && (
            <div
              className="text-xs rounded-lg px-3 py-2.5 animate-fade-in"
              style={{
                background: "var(--danger-bg)",
                border: "1px solid var(--danger-ring)",
                color: "var(--danger)",
              }}
            >
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="px-6 pb-6 flex items-center justify-between gap-3"
        >
          <button onClick={onDemo} className="text-xs text-muted hover:text-fg-2 transition-colors inline-flex items-center gap-1">
            Use TPC-H demo <ArrowRight size={12} strokeWidth={2.25} />
          </button>
          <button onClick={handleConnect} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading && <Loader2 size={14} strokeWidth={2.5} className="animate-spin" />}
            {loading ? "Connecting…" : "Connect"}
          </button>
        </div>
      </div>
    </div>
  );
}
