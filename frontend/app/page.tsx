"use client";
import { useState, useCallback } from "react";
import type { HistoryEntry } from "@/lib/types";
import { ask } from "@/lib/api";
import QueryBar from "@/components/QueryBar";
import ResultCard from "@/components/ResultCard";
import Sidebar from "@/components/Sidebar";

let idCounter = 0;

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleSubmit = useCallback(async (question: string) => {
    setLoading(true);
    setSubmitError(null);
    const t0 = Date.now();
    try {
      const response = await ask(question);
      const elapsed = (Date.now() - t0) / 1000;
      setHistory((h) => [
        { id: String(++idCounter), question, response, elapsed, timestamp: new Date() },
        ...h,
      ]);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="flex flex-col h-full min-h-screen">
      {/* Header */}
      <header className="border-b border-[#2a2d3a] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-lg font-bold text-white tracking-tight">NL2SQL</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-900/50 text-indigo-300 border border-indigo-700/50">
            TPC-H
          </span>
        </div>
        <a
          href="https://github.com"
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors"
        >
          GitHub
        </a>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <div className="p-6 overflow-y-auto">
          <Sidebar history={history} onSelect={handleSubmit} />
        </div>

        <main className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 max-w-4xl">
          <QueryBar onSubmit={handleSubmit} loading={loading} />

          {submitError && (
            <div className="text-sm text-red-400 bg-red-900/20 border border-red-800/40 rounded-lg px-4 py-3">
              {submitError}
            </div>
          )}

          {!loading && history.length === 0 && (
            <div className="flex-1 flex flex-col items-center justify-center text-center gap-3 py-20">
              <p className="text-3xl">🔍</p>
              <p className="text-slate-400 text-sm">Ask a question to query the TPC-H database.</p>
              <p className="text-slate-600 text-xs">Try: "Who are the top 5 customers by revenue?"</p>
            </div>
          )}

          {loading && (
            <div className="flex items-center gap-3 text-sm text-slate-400 py-4">
              <span className="w-4 h-4 border-2 border-slate-600 border-t-indigo-500 rounded-full animate-spin" />
              Generating SQL…
            </div>
          )}

          <div className="space-y-4">
            {history.map((entry) => (
              <ResultCard key={entry.id} entry={entry} />
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}
