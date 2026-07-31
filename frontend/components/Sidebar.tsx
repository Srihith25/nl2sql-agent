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
  tables?: string[];
}

function SidebarSection({ title }: { title: string }) {
  return (
    <h2
      className="text-xs font-semibold uppercase tracking-wider mb-2.5"
      style={{ color: "var(--fg-muted)" }}
    >
      {title}
    </h2>
  );
}

function SidebarButton({
  label,
  mono,
  onClick,
}: {
  label: string;
  mono?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left text-xs px-3 py-2 rounded-lg transition-all truncate"
      style={{ color: "var(--fg-2)", background: "transparent" }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background = "var(--accent-bg)";
        (e.currentTarget as HTMLButtonElement).style.color = "var(--accent)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLButtonElement).style.background = "transparent";
        (e.currentTarget as HTMLButtonElement).style.color = "var(--fg-2)";
      }}
    >
      <span className={mono ? "font-code" : ""}>{label}</span>
    </button>
  );
}

export default function Sidebar({ history, onSelect, tables }: Props) {
  const showTables = tables && tables.length > 0;

  return (
    <aside className="w-60 shrink-0 flex flex-col gap-6">
      {/* Tables or examples */}
      <div>
        <SidebarSection title={showTables ? "Tables" : "Examples"} />
        <ul className="space-y-0.5">
          {showTables
            ? tables.map((t) => (
                <li key={t}>
                  <SidebarButton
                    label={t}
                    mono
                    onClick={() => onSelect(`Show me a sample of the ${t} table`)}
                  />
                </li>
              ))
            : EXAMPLES.map((ex) => (
                <li key={ex}>
                  <SidebarButton label={ex} onClick={() => onSelect(ex)} />
                </li>
              ))}
        </ul>
      </div>

      {/* Recent history */}
      {history.length > 0 && (
        <div>
          <SidebarSection title="Recent" />
          <ul className="space-y-0.5">
            {history.slice(0, 8).map((h) => (
              <li key={h.id}>
                <SidebarButton label={h.question} onClick={() => onSelect(h.question)} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
