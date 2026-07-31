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
  session_id: string | null;
  explanation: string | null;
  follow_up_questions: string[];
  verified?: boolean | null;
  verify_sql?: string | null;
}

export interface HistoryEntry {
  id: string;
  question: string;
  response: QueryResponse;
  elapsed: number;
  timestamp: Date;
}

export interface ConnectResponse {
  session_id: string;
  label: string;
  tables: string[];
}

export interface ActiveSession {
  session_id: string;
  label: string;
  tables: string[];
}
