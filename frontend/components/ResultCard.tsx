"use client";
import { useState } from "react";
import type { HistoryEntry } from "@/lib/types";
import DataTable from "./DataTable";
import SqlBlock from "./SqlBlock";
import ResultChart from "./ResultChart";
import { CircleCheck, TriangleAlert, ChevronRight } from "lucide-react";

interface Props {
  entry: HistoryEntry;
  onFollowUp: (q: string) => void;
}

export default function ResultCard({ entry, onFollowUp }: Props) {
  const { question, response, elapsed } = entry;
  const { sql, rows, chart_suggestion, validation_error, attempts, error, explanation, follow_up_questions, verified, verify_sql } = response;
  const [sqlOpen, setSqlOpen] = useState(false);

  const isSingleValue = rows.length === 1 && Object.keys(rows[0]).length === 1;
  const hasData = rows.length > 0 && !error;

  return (
    <div
      className="rounded-2xl overflow-hidden animate-fade-in transition-all"
      style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      {/* Question header */}
      <div
        className="px-5 py-3.5 flex items-start justify-between gap-4"
        style={{ borderBottom: "1px solid var(--border)", background: "var(--surface-2)" }}
      >
        <p className="text-sm font-medium" style={{ color: "var(--fg)" }}>{question}</p>
        <div className="flex items-center gap-2 shrink-0 mt-0.5">
          {verified === true && (
            <span
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
              title={verify_sql ? `Verified by: ${verify_sql}` : "A second independent SQL produced the same result"}
              style={{
                background: "var(--success-bg)",
                border: "1px solid var(--success-ring)",
                color: "var(--success)",
              }}
            >
              <CircleCheck size={12} strokeWidth={2.25} /> Verified
            </span>
          )}
          {verified === false && (
            <span
              className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium"
              title={verify_sql ? `Verifier SQL: ${verify_sql}` : "A second independent SQL returned different results"}
              style={{
                background: "var(--warning-bg)",
                border: "1px solid var(--warning-ring)",
                color: "var(--warning)",
              }}
            >
              <TriangleAlert size={12} strokeWidth={2.25} /> Unverified
            </span>
          )}
          <span className="text-xs" style={{ color: "var(--fg-muted)" }}>
            {elapsed.toFixed(1)}s
          </span>
        </div>
      </div>

      <div className="px-5 py-4 space-y-4">
        {/* Error */}
        {error && (
          <div
            className="text-sm rounded-xl px-4 py-3 animate-fade-in"
            style={{
              background: "var(--danger-bg)",
              border: "1px solid var(--danger-ring)",
              color: "var(--danger)",
            }}
          >
            {error}
          </div>
        )}

        {/* Validation warning */}
        {validation_error && !error && (
          <div
            className="text-sm rounded-xl px-4 py-3 animate-fade-in"
            style={{
              background: "var(--warning-bg)",
              border: "1px solid var(--warning-ring)",
              color: "var(--warning)",
            }}
          >
            {validation_error}
          </div>
        )}

        {/* Single scalar value */}
        {isSingleValue && !error && (
          <div className="text-center py-8">
            <p className="text-5xl font-bold tracking-tight gradient-text">
              {String(Object.values(rows[0])[0])}
            </p>
            <p className="text-xs mt-2" style={{ color: "var(--fg-muted)" }}>
              {Object.keys(rows[0])[0]}
            </p>
          </div>
        )}

        {/* Chart + table */}
        {!isSingleValue && hasData && (
          <div className="space-y-4">
            {chart_suggestion?.type && chart_suggestion.type !== "none" &&
              chart_suggestion.x && chart_suggestion.y && rows.length >= 2 && (
              <div
                className="rounded-xl p-4"
                style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
              >
                <ResultChart rows={rows} suggestion={chart_suggestion} />
              </div>
            )}
            <DataTable rows={rows} />
          </div>
        )}

        {/* Natural language explanation */}
        {explanation && hasData && (
          <div
            className="rounded-xl px-4 py-3 text-sm leading-relaxed animate-fade-in"
            style={{
              background: "var(--accent-bg)",
              border: "1px solid var(--accent-ring)",
              color: "var(--fg-2)",
            }}
          >
            <span
              className="inline-block text-xs font-semibold uppercase tracking-wide mr-2"
              style={{ color: "var(--accent)" }}
            >
              Analysis
            </span>
            {explanation}
          </div>
        )}

        {/* Follow-up question chips */}
        {follow_up_questions && follow_up_questions.length > 0 && hasData && (
          <div className="space-y-2 animate-fade-in">
            <p className="text-xs font-medium" style={{ color: "var(--fg-muted)" }}>
              Ask a follow-up
            </p>
            <div className="flex flex-wrap gap-2">
              {follow_up_questions.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onFollowUp(q)}
                  className="text-xs px-3 py-1.5 rounded-full transition-all text-left"
                  style={{
                    background: "var(--surface-2)",
                    border: "1px solid var(--border)",
                    color: "var(--fg-2)",
                  }}
                  onMouseEnter={(e) => {
                    const el = e.currentTarget;
                    el.style.background = "var(--accent-bg)";
                    el.style.borderColor = "var(--accent)";
                    el.style.color = "var(--accent)";
                  }}
                  onMouseLeave={(e) => {
                    const el = e.currentTarget;
                    el.style.background = "var(--surface-2)";
                    el.style.borderColor = "var(--border)";
                    el.style.color = "var(--fg-2)";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* SQL toggle */}
        {sql && (
          <div>
            <button
              onClick={() => setSqlOpen((o) => !o)}
              className="flex items-center gap-1 text-xs transition-colors"
              style={{ color: sqlOpen ? "var(--accent)" : "var(--fg-muted)" }}
            >
              <ChevronRight
                size={14}
                strokeWidth={2.25}
                className="transition-transform duration-150"
                style={{ transform: sqlOpen ? "rotate(90deg)" : "rotate(0deg)" }}
              />
              <span>View SQL</span>
            </button>
            {sqlOpen && (
              <div className="mt-2 animate-fade-in">
                <SqlBlock sql={sql} attempts={attempts} />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
