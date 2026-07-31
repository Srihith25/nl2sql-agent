"use client";
import { Database, MessageSquareText, Table2, ShieldCheck, ArrowRight, PlayCircle } from "lucide-react";

interface Props {
  onGetStarted: () => void;
  onTryDemo: () => void;
}

const STEPS = [
  {
    Icon: Database,
    title: "Connect a database",
    body: "Paste a Postgres/MySQL/SQLite/DuckDB connection string, or upload a CSV, Parquet, SQLite, or DuckDB file. Or skip this — the built-in TPC-H demo works with no setup.",
  },
  {
    Icon: MessageSquareText,
    title: "Ask a question in plain English",
    body: "“Who are the top 5 customers by revenue?”, “Show monthly revenue for 1995” — no SQL required.",
  },
  {
    Icon: Table2,
    title: "Get validated SQL, results, and a chart",
    body: "Every query is parsed and dry-run before it touches your data. If it fails, the agent rewrites and retries automatically — you only see the final answer.",
  },
  {
    Icon: ShieldCheck,
    title: "Toggle “Verify” for a second opinion",
    body: "Turns on an independent second SQL query to cross-check the answer, flagged Verified or Unverified.",
  },
];

export default function WelcomeScreen({ onGetStarted, onTryDemo }: Props) {
  return (
    <div className="flex flex-col h-full min-h-screen bg-page">
      <div className="flex-1 flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-2xl animate-fade-in">
          {/* Logo lockup */}
          <div className="flex flex-col items-center text-center gap-3 mb-10">
            <span className="logo-mark" style={{ width: "2.5rem", height: "2.5rem", borderRadius: "0.75rem" }}>
              <Database size={22} strokeWidth={2.25} />
            </span>
            <h1 className="text-2xl font-bold text-fg tracking-tight">NL2SQL</h1>
            <p className="text-sm text-muted max-w-md">
              Ask any database a question in plain English. Self-healing SQL generation,
              schema-aware retrieval, and an optional independent double-check on every answer.
            </p>
          </div>

          {/* Steps */}
          <div
            className="rounded-2xl overflow-hidden mb-8"
            style={{ background: "var(--surface)", border: "1px solid var(--border)", boxShadow: "var(--shadow-sm)" }}
          >
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className="flex items-start gap-4 px-5 py-4"
                style={i > 0 ? { borderTop: "1px solid var(--border)" } : undefined}
              >
                <span
                  className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold"
                  style={{ background: "var(--accent-bg)", color: "var(--accent)", border: "1px solid var(--accent-ring)" }}
                >
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <step.Icon size={14} strokeWidth={2.25} style={{ color: "var(--fg-muted)" }} />
                    <p className="text-sm font-medium text-fg">{step.title}</p>
                  </div>
                  <p className="text-xs text-muted leading-relaxed">{step.body}</p>
                </div>
              </div>
            ))}
          </div>

          {/* CTAs */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
            <button onClick={onGetStarted} className="btn-primary flex items-center gap-2 w-full sm:w-auto justify-center">
              Connect your database <ArrowRight size={14} strokeWidth={2.5} />
            </button>
            <button
              onClick={onTryDemo}
              className="btn-ghost flex items-center gap-2 w-full sm:w-auto justify-center"
            >
              <PlayCircle size={14} strokeWidth={2} />
              Try the demo first
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
