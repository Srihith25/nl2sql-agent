"use client";
import { useState } from "react";
import type { HistoryEntry } from "@/lib/types";
import DataTable from "./DataTable";
import SqlBlock from "./SqlBlock";
import ResultChart from "./ResultChart";

interface Props {
  entry: HistoryEntry;
}

export default function ResultCard({ entry }: Props) {
  const { question, response, elapsed } = entry;
  const { sql, rows, chart_suggestion, validation_error, attempts, error } = response;
  const [sqlOpen, setSqlOpen] = useState(false);

  const isSingleValue = rows.length === 1 && Object.keys(rows[0]).length === 1;

  return (
    <div className="rounded-xl border border-[#2a2d3a] bg-[#1a1d27] overflow-hidden">
      <div className="px-5 py-4 border-b border-[#2a2d3a] flex items-start justify-between gap-4">
        <p className="text-sm font-medium text-slate-200">{question}</p>
        <span className="text-xs text-slate-500 whitespace-nowrap">{elapsed.toFixed(1)}s</span>
      </div>

      <div className="px-5 py-4 space-y-4">
        {error && (
          <div className="text-sm text-red-400 bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-3">
            {error}
          </div>
        )}
        {validation_error && !error && (
          <div className="text-sm text-amber-400 bg-amber-900/20 border border-amber-800/40 rounded-lg px-4 py-3">
            {validation_error}
          </div>
        )}

        {isSingleValue && !error && (
          <div className="text-center py-6">
            <p className="text-4xl font-bold text-indigo-400">
              {String(Object.values(rows[0])[0])}
            </p>
            <p className="text-xs text-slate-500 mt-1">{Object.keys(rows[0])[0]}</p>
          </div>
        )}

        {!isSingleValue && rows.length > 0 && !error && (
          <div className="space-y-4">
            {chart_suggestion?.type && chart_suggestion.type !== "none" && (
              <ResultChart rows={rows} suggestion={chart_suggestion} />
            )}
            <DataTable rows={rows} />
          </div>
        )}

        {sql && (
          <div>
            <button
              onClick={() => setSqlOpen((o) => !o)}
              className="text-xs text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1"
            >
              <span>{sqlOpen ? "▾" : "▸"}</span>
              <span>SQL</span>
            </button>
            {sqlOpen && <div className="mt-2"><SqlBlock sql={sql} attempts={attempts} /></div>}
          </div>
        )}
      </div>
    </div>
  );
}
