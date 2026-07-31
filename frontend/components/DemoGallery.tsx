"use client";
import { X } from "lucide-react";

interface Props {
  onClose: () => void;
}

const SCREENSHOTS = [
  { src: "/media/screenshots/1-welcome.png", caption: "Start here — a short walkthrough before you connect anything" },
  { src: "/media/screenshots/2-connect-database.png", caption: "Connect Postgres/MySQL/SQLite/DuckDB, or upload a file" },
  { src: "/media/screenshots/3-result-light.png", caption: "Question → validated SQL → results, chart, and a plain-English analysis" },
  { src: "/media/screenshots/4-result-dark.png", caption: "Dark mode" },
  { src: "/media/screenshots/5-sql-view.png", caption: "The exact generated SQL is always one click away" },
];

export default function DemoGallery({ onClose }: Props) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(8px)" }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-3xl max-h-[90vh] overflow-y-auto animate-fade-in"
        style={{
          background: "var(--surface)",
          border: "1px solid var(--border)",
          borderRadius: "1.25rem",
          boxShadow: "var(--shadow-lg)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className="sticky top-0 z-10 px-6 py-4 flex items-center justify-between"
          style={{ background: "var(--surface)", borderBottom: "1px solid var(--border)" }}
        >
          <div>
            <h2 className="text-base font-semibold text-fg">See it in action</h2>
            <p className="text-xs text-muted mt-0.5">A quick walkthrough, plus a few screenshots</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors"
            style={{ color: "var(--fg-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--surface-2)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            aria-label="Close"
          >
            <X size={16} strokeWidth={2.25} />
          </button>
        </div>

        <div className="px-6 py-5 space-y-6">
          <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
            <video controls preload="metadata" className="w-full block" style={{ background: "#000" }}>
              <source src="/media/demo.mp4" type="video/mp4" />
              Your browser doesn&apos;t support inline video — the file is at /media/demo.mp4.
            </video>
          </div>

          <div className="space-y-4">
            {SCREENSHOTS.map((s) => (
              <figure key={s.src}>
                <div className="rounded-xl overflow-hidden" style={{ border: "1px solid var(--border)" }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.src} alt={s.caption} className="w-full block" />
                </div>
                <figcaption className="text-xs text-muted mt-2">{s.caption}</figcaption>
              </figure>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
