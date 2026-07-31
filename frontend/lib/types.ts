export interface ChartSuggestion {
  type?: "bar" | "line" | "none";
  x?: string;
  y?: string;
}

export interface QueryResponse {
  sql: string | null;
  cube_query: Record<string, unknown> | null;
  rows: Record<string, unknown>[];
  chart_suggestion: ChartSuggestion;
  validation_error: string | null;
  attempts: number;
  error: string | null;
}

export interface HistoryEntry {
  id: string;
  question: string;
  response: QueryResponse;
  elapsed: number;
  timestamp: Date;
}
