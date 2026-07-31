"use client";

interface Props {
  rows: Record<string, unknown>[];
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") {
    return Number.isInteger(v)
      ? v.toLocaleString()
      : v.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  return String(v);
}

const CAP = 50;

export default function DataTable({ rows }: Props) {
  if (!rows.length)
    return <p className="text-xs text-muted italic py-2">No rows returned.</p>;

  const display = rows.slice(0, CAP);
  const cols = Object.keys(display[0]);

  return (
    <div className="overflow-auto rounded-xl" style={{ border: "1px solid var(--border)" }}>
      <table className="min-w-full text-xs">
        <thead>
          <tr style={{ background: "var(--surface-2)", borderBottom: "1px solid var(--border)" }}>
            {cols.map((c) => (
              <th
                key={c}
                className="px-4 py-2.5 text-left font-semibold whitespace-nowrap tracking-wide uppercase"
                style={{ color: "var(--fg-muted)", fontSize: "0.68rem" }}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {display.map((row, i) => (
            <tr
              key={i}
              className="transition-colors"
              style={{ background: i % 2 === 0 ? "var(--surface)" : "var(--surface-2)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-bg)")}
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = i % 2 === 0 ? "var(--surface)" : "var(--surface-2)")
              }
            >
              {cols.map((c) => (
                <td
                  key={c}
                  className="px-4 py-2.5 whitespace-nowrap font-code"
                  style={{ color: "var(--fg-2)", borderTop: "1px solid var(--border)" }}
                >
                  {fmt(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > CAP && (
        <div
          className="px-4 py-2 text-xs text-muted"
          style={{ borderTop: "1px solid var(--border)", background: "var(--surface-2)" }}
        >
          Showing {CAP} of {rows.length} rows
        </div>
      )}
    </div>
  );
}
