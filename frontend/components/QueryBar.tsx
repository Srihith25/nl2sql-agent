"use client";
import { useState, type FormEvent, type KeyboardEvent } from "react";
import { ArrowUp, Loader2 } from "lucide-react";

interface Props {
  onSubmit: (q: string) => void;
  loading: boolean;
}

export default function QueryBar({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("");

  function submit() {
    const q = value.trim();
    if (q && !loading) { onSubmit(q); setValue(""); }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  }

  return (
    <div
      className="rounded-xl overflow-hidden transition-all duration-200"
      style={{
        background: "var(--surface)",
        border: "1.5px solid var(--border)",
        boxShadow: "var(--shadow-sm)",
      }}
      onFocusCapture={(e) => {
        const el = e.currentTarget as HTMLDivElement;
        el.style.borderColor = "var(--accent)";
        el.style.boxShadow = "0 0 0 3px var(--accent-ring)";
      }}
      onBlurCapture={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) {
          const el = e.currentTarget as HTMLDivElement;
          el.style.borderColor = "var(--border)";
          el.style.boxShadow = "var(--shadow-sm)";
        }
      }}
    >
      <textarea
        rows={2}
        className="w-full resize-none px-4 pt-3.5 pb-1 text-sm outline-none"
        style={{
          background: "transparent",
          color: "var(--fg)",
        }}
        placeholder="Ask a question about your data… (Enter to submit, Shift+Enter for new line)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <div className="flex items-center justify-between px-3 pb-2.5">
        <span className="text-xs text-muted">
          {value.length > 0 ? `${value.length} chars` : "Enter ↵ to submit"}
        </span>
        <button
          onClick={submit}
          disabled={loading || !value.trim()}
          className="btn-primary flex items-center gap-1.5 py-1.5 px-4 text-xs"
        >
          {loading ? (
            <>
              <Loader2 size={13} strokeWidth={2.5} className="animate-spin" />
              Running
            </>
          ) : (
            <>
              Ask <ArrowUp size={13} strokeWidth={2.5} />
            </>
          )}
        </button>
      </div>
    </div>
  );
}
