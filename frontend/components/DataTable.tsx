"use client";

interface Props {
  rows: Record<string, unknown>[];
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(v);
}

const CAP = 50;

export default function DataTable({ rows }: Props) {
  if (!rows.length) return <p className="text-sm text-slate-500 italic">No rows returned.</p>;

  const display = rows.slice(0, CAP);
  const cols = Object.keys(display[0]);

  return (
    <div className="overflow-auto rounded-lg border border-[#2a2d3a]">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="bg-[#1a1d27] border-b border-[#2a2d3a]">
            {cols.map((c) => (
              <th key={c} className="px-4 py-2 text-left font-medium text-slate-400 whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {display.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-[#0f1117]" : "bg-[#13161f]"}>
              {cols.map((c) => (
                <td key={c} className="px-4 py-2 text-slate-300 whitespace-nowrap">
                  {fmt(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > CAP && (
        <p className="px-4 py-2 text-xs text-slate-500 border-t border-[#2a2d3a]">
          Showing {CAP} of {rows.length} rows
        </p>
      )}
    </div>
  );
}
