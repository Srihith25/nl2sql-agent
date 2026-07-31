"use client";
import { useTheme } from "next-themes";
import {
  BarChart, Bar, LineChart, Line,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import type { ChartSuggestion } from "@/lib/types";

interface Props {
  rows: Record<string, unknown>[];
  suggestion: ChartSuggestion;
}

export default function ResultChart({ rows, suggestion }: Props) {
  const { resolvedTheme } = useTheme();
  const dark = resolvedTheme === "dark";

  const colors = {
    bar:     dark ? "#f0b429" : "#b45309",
    grid:    dark ? "#262f3d" : "#e2e8f0",
    tick:    dark ? "#576274" : "#94a3b8",
    tooltip: dark ? "#0d1117" : "#ffffff",
    border:  dark ? "#262f3d" : "#e2e8f0",
    text:    dark ? "#f1f5f9" : "#0f172a",
  };

  const { type, x, y } = suggestion;
  if (!type || type === "none" || !x || !y || rows.length < 2) return null;

  const commonAxis = {
    tick: { fill: colors.tick, fontSize: 11 },
    tickLine: false,
    axisLine: { stroke: colors.grid },
  };

  const tooltipStyle = {
    contentStyle: {
      background: colors.tooltip,
      border: `1px solid ${colors.border}`,
      borderRadius: 10,
      fontSize: 12,
      color: colors.text,
      boxShadow: dark ? "0 8px 32px rgba(0,0,0,0.4)" : "0 4px 12px rgba(0,0,0,0.08)",
    },
    labelStyle: { fontWeight: 600 },
    cursor: { fill: dark ? "rgba(240,180,41,0.06)" : "rgba(180,83,9,0.06)" },
  };

  if (type === "line") {
    return (
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={rows} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
          <XAxis dataKey={x} {...commonAxis} />
          <YAxis {...commonAxis} width={48} />
          <Tooltip {...tooltipStyle} />
          <Line
            type="monotone"
            dataKey={y}
            stroke={colors.bar}
            strokeWidth={2.5}
            dot={false}
            activeDot={{ r: 4, strokeWidth: 0, fill: colors.bar }}
          />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={rows} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
        <XAxis dataKey={x} {...commonAxis} />
        <YAxis {...commonAxis} width={48} />
        <Tooltip {...tooltipStyle} />
        <Bar dataKey={y} fill={colors.bar} radius={[5, 5, 0, 0]} maxBarSize={40} />
      </BarChart>
    </ResponsiveContainer>
  );
}
