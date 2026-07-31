"use client";
import { useState, useCallback } from "react";
import type { ActiveSession, HistoryEntry } from "@/lib/types";
import { ask } from "@/lib/api";
import QueryBar from "@/components/QueryBar";
import ResultCard from "@/components/ResultCard";
import Sidebar from "@/components/Sidebar";
import ConnectModal from "@/components/ConnectModal";
import ThemeToggle from "@/components/ThemeToggle";
import WelcomeScreen from "@/components/WelcomeScreen";
import { Database, ShieldCheck, ShieldOff, Search } from "lucide-react";

let idCounter = 0;

type Stage = "welcome" | "connect" | "app";

export default function Home() {
  const [stage, setStage] = useState<Stage>("welcome");
  const [session, setSession] = useState<ActiveSession | null>(null);
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [verifyMode, setVerifyMode] = useState(false);

  const handleConnect = useCallback((s: ActiveSession) => {
    setSession(s);
    setStage("app");
    setHistory([]);
  }, []);

  const handleDemo = useCallback(() => {
    setSession(null);
    setStage("app");
    setHistory([]);
  }, []);

  const handleSubmit = useCallback(async (question: string) => {
    setLoading(true);
    setSubmitError(null);
    const t0 = Date.now();
    try {
      const response = await ask(question, session?.session_id, verifyMode);
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
  }, [session]);

  if (stage === "welcome") {
    return <WelcomeScreen onGetStarted={() => setStage("connect")} onTryDemo={handleDemo} />;
  }

  return (
    <div className="flex flex-col h-full min-h-screen bg-page">
      {stage === "connect" && (
        <ConnectModal onConnect={handleConnect} onDemo={handleDemo} />
      )}

      {/* Header */}
      <header className="glass-header sticky top-0 z-30 px-5 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <span className="flex items-center gap-2 shrink-0">
            <span className="logo-mark">
              <Database size={15} strokeWidth={2.25} />
            </span>
            <span className="text-base font-bold text-fg tracking-tight">NL2SQL</span>
          </span>
          {session ? (
            <span
              className="badge truncate max-w-[180px]"
              style={{
                background: "var(--success-bg)",
                color: "var(--success)",
                borderColor: "var(--success-ring)",
              }}
            >
              {session.label}
            </span>
          ) : (
            <span
              className="badge shrink-0"
              style={{ background: "var(--accent-bg)", color: "var(--accent)", borderColor: "var(--accent-ring)" }}
            >
              TPC-H Demo
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <ThemeToggle />
          <button
            onClick={() => setVerifyMode((v) => !v)}
            title="Run a second independent SQL to verify every answer"
            className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg transition-all"
            style={{
              background: verifyMode ? "var(--accent-bg)" : "var(--surface-2)",
              border: `1px solid ${verifyMode ? "var(--accent-ring)" : "var(--border)"}`,
              color: verifyMode ? "var(--accent)" : "var(--fg-muted)",
            }}
          >
            {verifyMode ? <ShieldCheck size={13} strokeWidth={2.25} /> : <ShieldOff size={13} strokeWidth={2} />}
            {verifyMode ? "Verify on" : "Verify off"}
          </button>
          <button
            onClick={() => setStage("connect")}
            className="btn-ghost text-xs"
          >
            {session ? "Switch DB" : "Connect DB"}
          </button>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <div className="hidden md:block overflow-y-auto shrink-0">
          <Sidebar history={history} onSelect={handleSubmit} tables={session?.tables} />
        </div>

        {/* Main */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 flex flex-col gap-5">
            <QueryBar onSubmit={handleSubmit} loading={loading} />

            {submitError && (
              <div
                className="text-sm rounded-xl px-4 py-3 animate-fade-in"
                style={{
                  background: "var(--danger-bg)",
                  border: "1px solid var(--danger-ring)",
                  color: "var(--danger)",
                }}
              >
                {submitError}
              </div>
            )}

            {loading && (
              <div className="flex items-center gap-3 py-2 animate-fade-in">
                <div className="dot-flashing">
                  <span /><span /><span />
                </div>
                <span className="text-sm text-muted">Generating SQL…</span>
              </div>
            )}

            {!loading && history.length === 0 && (
              <div className="flex flex-col items-center justify-center text-center gap-4 py-24 animate-fade-in">
                <div
                  className="w-14 h-14 rounded-2xl flex items-center justify-center"
                  style={{ background: "var(--accent-bg)", border: "1px solid var(--accent-ring)", color: "var(--accent)" }}
                >
                  <Search size={22} strokeWidth={2} />
                </div>
                <div>
                  <p className="text-fg font-medium text-sm mb-1">
                    {session ? `Connected to ${session.label}` : "TPC-H demo ready"}
                  </p>
                  <p className="text-muted text-xs">
                    {session
                      ? "Ask a question about your data in plain English"
                      : 'Ask a question — try "Who are the top 5 customers by revenue?"'}
                  </p>
                </div>
                {session && session.tables.length > 0 && (
                  <p className="text-xs" style={{ color: "var(--fg-muted)" }}>
                    {session.tables.slice(0, 5).join(" · ")}
                    {session.tables.length > 5 && ` · +${session.tables.length - 5} more`}
                  </p>
                )}
              </div>
            )}

            <div className="flex flex-col gap-4">
              {history.map((entry, i) => (
                <div key={entry.id} className={i === 0 ? "animate-fade-in" : undefined}>
                  <ResultCard entry={entry} onFollowUp={handleSubmit} />
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
