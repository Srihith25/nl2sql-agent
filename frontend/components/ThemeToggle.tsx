"use client";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Sun, Monitor, Moon } from "lucide-react";

const options = [
  { value: "light",  label: "Light",  Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark",   label: "Dark",   Icon: Moon },
] as const;

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Avoid hydration mismatch — only render after mount
  useEffect(() => setMounted(true), []);
  if (!mounted) return <div className="w-[108px] h-8 rounded-lg" style={{ background: "var(--surface-2)" }} />;

  return (
    <div
      className="flex items-center rounded-lg p-0.5 gap-0.5"
      style={{ background: "var(--surface-2)", border: "1px solid var(--border)" }}
    >
      {options.map((opt) => {
        const active = theme === opt.value;
        return (
          <button
            key={opt.value}
            onClick={() => setTheme(opt.value)}
            title={opt.label}
            className="relative flex items-center justify-center w-8 h-7 rounded-md transition-all duration-200"
            style={{
              background: active ? "var(--surface)" : "transparent",
              color: active ? "var(--accent)" : "var(--fg-muted)",
              boxShadow: active ? "var(--shadow-sm)" : "none",
            }}
          >
            <opt.Icon size={14} strokeWidth={2.25} />
          </button>
        );
      })}
    </div>
  );
}
