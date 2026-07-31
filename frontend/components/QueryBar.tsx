"use client";
import { useState, type FormEvent, type KeyboardEvent } from "react";

interface Props {
  onSubmit: (q: string) => void;
  loading: boolean;
}

export default function QueryBar({ onSubmit, loading }: Props) {
  const [value, setValue] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const q = value.trim();
    if (q && !loading) {
      onSubmit(q);
      setValue("");
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const q = value.trim();
      if (q && !loading) {
        onSubmit(q);
        setValue("");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end">
      <textarea
        rows={2}
        className="flex-1 resize-none rounded-lg bg-[#1a1d27] border border-[#2a2d3a] px-4 py-3 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
        placeholder="Ask a question about your data… (Enter to submit)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !value.trim()}
        className="h-[62px] px-5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
      >
        {loading ? (
          <>
            <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <span>Running</span>
          </>
        ) : (
          "Ask"
        )}
      </button>
    </form>
  );
}
