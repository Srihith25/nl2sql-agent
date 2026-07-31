"use client";
import { useState } from "react";

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
    <div className="relative group">
      <pre className="bg-[#0d0f14] border border-[#2a2d3a] rounded-lg px-4 py-3 text-xs text-slate-300 overflow-auto whitespace-pre-wrap">
        {sql}
      </pre>
      <div className="absolute top-2 right-2 flex items-center gap-2">
        {attempts !== undefined && attempts > 1 && (
          <span className="text-xs px-2 py-0.5 rounded bg-amber-900/50 text-amber-300 border border-amber-700/50">
            {attempts} attempts
          </span>
        )}
        <button
          onClick={copy}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-xs px-2 py-1 rounded bg-[#2a2d3a] text-slate-400 hover:text-white"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
}
