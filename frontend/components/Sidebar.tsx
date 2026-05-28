"use client";
import type { HistoryEntry } from "@/lib/types";

const EXAMPLES = [
  "Who are the top 5 customers by revenue?",
  "What are the most ordered part names?",
  "Show me monthly revenue for 1995",
  "Which suppliers are in Germany?",
  "What is the total revenue by region?",
  "How many orders were placed each year?",
];

interface Props {
  history: HistoryEntry[];
  onSelect: (q: string) => void;
}

export default function Sidebar({ history, onSelect }: Props) {
  return (
    <aside className="w-64 shrink-0 flex flex-col gap-6">
      <div>
        <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Examples</h2>
        <ul className="space-y-1">
          {EXAMPLES.map((ex) => (
            <li key={ex}>
              <button
                onClick={() => onSelect(ex)}
                className="w-full text-left text-xs text-slate-400 hover:text-slate-200 hover:bg-[#1a1d27] px-3 py-2 rounded-lg transition-colors"
              >
                {ex}
              </button>
            </li>
          ))}
        </ul>
      </div>

      {history.length > 0 && (
        <div>
          <h2 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Recent</h2>
          <ul className="space-y-1">
            {history.slice(0, 8).map((h) => (
              <li key={h.id}>
                <button
                  onClick={() => onSelect(h.question)}
                  className="w-full text-left text-xs text-slate-400 hover:text-slate-200 hover:bg-[#1a1d27] px-3 py-2 rounded-lg transition-colors truncate"
                >
                  {h.question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
