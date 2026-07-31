"use client";
import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface Props {
  sql: string;
  attempts?: number;
}

export default function SqlBlock({ sql, attempts }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="relative group rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
      {/* Toolbar */}
      <div
        className="flex items-center justify-between px-4 py-2"
        style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}
      >
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium" style={{ color: "var(--fg-muted)" }}>SQL</span>
          {attempts !== undefined && attempts > 1 && (
            <span
              className="badge"
              style={{
                background: "var(--warning-bg)",
                color: "var(--warning)",
                borderColor: "var(--warning-ring)",
                fontSize: "0.65rem",
              }}
            >
              {attempts} attempts
            </span>
          )}
        </div>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg transition-all"
          style={{
            color: copied ? "var(--success)" : "var(--fg-muted)",
            background: copied ? "var(--success-bg)" : "transparent",
            border: "1px solid var(--border)",
          }}
        >
          {copied ? <Check size={12} strokeWidth={2.5} /> : <Copy size={12} strokeWidth={2} />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>

      {/* Code */}
      <pre
        className="px-4 py-3 overflow-auto text-xs font-code leading-relaxed"
        style={{ background: "var(--surface)", color: "var(--fg-2)", maxHeight: "320px" }}
      >
        {sql}
      </pre>
    </div>
  );
}
