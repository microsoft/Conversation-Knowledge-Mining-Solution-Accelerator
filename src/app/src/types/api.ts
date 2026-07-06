/**
 * TypeScript interfaces for all backend API responses and request payloads.
 * Replaces `any` usage across the frontend.
 */

// ── Common ──

export interface Source {
  doc_id: string;
  score: number;
  text?: string;
  filename?: string;
  source_file?: string;
  url?: string;
  metadata?: Record<string, unknown>;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  timestamp?: string;
}

// ── Ingestion ──

export interface UploadedFile {
  id: string;
  filename: string;
  doc_count: number;
  summary: string;
  keywords: string[];
  filter_values: Record<string, string[]>;
  doc_ids: string[];
  uploaded_at: string;
  status?: "uploading" | "processing" | "ready" | "error" | "failed";
  error?: string;
  error_message?: string;
}

export interface DocumentRecord {
  id: string;
  type: string;
  text: string;
  metadata: Record<string, unknown>;
}

export interface IngestionStats {
  total_documents: number;
  total_files: number;
  by_type: Record<string, number>;
}

export interface FilterValue {
  value: string;
  label: string;
  count: number;
}

export interface FilterDimension {
  id: string;
  label: string;
  type: string;
  values: FilterValue[];
}

export interface FilterSchema {
  domain: string;
  dimensions: FilterDimension[];
}

// ── RAG / Chat ──

export interface QAResponse {
  answer: string;
  sources: Source[];
  tokens_used?: number;
}

export interface ChatSession {
  id: string;
  title: string;
  user_id: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

// ── Dashboard / Insights ──

export interface KPI {
  label: string;
  value: number | string;
  format?: "percentage" | "minutes" | "number" | "currency";
  trend?: "up" | "down" | "flat";
  confidence?: number;
}

export interface ChartDataPoint {
  label?: string;
  value?: number;
  text?: string;
  frequency?: number;
  weight?: number;
}

export interface ChartSpec {
  id: string;
  title: string;
  description?: string;
  visualization: "donut" | "bar" | "horizontal_bar" | "line" | "word_cloud" | "table" | "trending_table" | "driver_table";
  data: ChartDataPoint[];
  confidence?: number;
  sectionId?: string;
}

export interface DashboardSection {
  id: string;
  title: string;
  charts: ChartSpec[];
}

export interface DashboardFilter {
  field: string;
  label: string;
  type: string;
  multi_select: boolean;
  values: string[];
}

export interface RuntimeKPI {
  id: string;
  label: string;
  value: number | string;
  format?: "percentage" | "minutes" | "number" | "currency";
  trendDirection?: "up" | "down" | "stable";
  trendValue?: number | null;
  confidence?: number | null;
}

export interface RuntimeTopic {
  id: string;
  name: string;
  score: number;
  trendValue?: number | null;
  trendDirection?: "up" | "down" | "stable";
}

export interface RuntimeEntity {
  id: string;
  name: string;
  mentions: number;
  trendDirection?: "up" | "down" | "stable";
  trendValue?: number | null;
}

export interface RuntimeRelationship {
  from: string;
  to: string;
  relation?: string;
  strength: number;
}

export interface EvidenceItem {
  text: string;
  label?: string;
  value?: number | string;
  section?: string;
}

export interface RuntimeInsight {
  id: string;
  category: "Anomaly" | "Risk" | "Opportunity" | "Trend" | "Insight";
  title: string;
  confidence?: number | null;
  impactScore?: number;
  context?: string;
  explanation?: string;
  evidenceCount?: number;
  evidence?: EvidenceItem[];
}

export interface UnexpectedPattern {
  id: string;
  pattern: string;
  severity: "high" | "medium" | "low";
  explanation: string;
}

export interface RuntimeAction {
  id: string;
  label: string;
  intentType?: string;
}

export interface SentimentAnalysis {
  positive: number;
  neutral: number;
  negative: number;
}

export interface TimelineEvent {
  date: string;
  event: string;
  change: "positive" | "negative" | "neutral" | "alert";
}

export interface InsightRuntime {
  schemaVersion: string;
  generatedAt: string;
  recordCount: number;
  counts?: {
    topics: number;
    entities: number;
    relationships: number;
  };
  summarySignals: string[];
  kpis: RuntimeKPI[];
  topics: RuntimeTopic[];
  entities: RuntimeEntity[];
  relationships: RuntimeRelationship[];
  insights: RuntimeInsight[];
  unexpectedPatterns?: UnexpectedPattern[];
  actions: RuntimeAction[];
  sentiment?: SentimentAnalysis;
  events?: TimelineEvent[];
}

export interface DashboardResponse {
  datasetInfo?: {
    name: string;
    sourceType: string;
    lastUpdated: string;
  };
  data_context: {
    total_records: number;
    filtered_records: number;
    filters_applied: Record<string, string>;
  };
  headline: string;
  summary: string;
  key_insights: string[];
  standout_findings: string[];
  kpis: KPI[];
  sections: DashboardSection[];
  filters: DashboardFilter[];
  suggested_questions: string[];
  runtime?: InsightRuntime;
}

// ── Data Sources ──

export interface FieldMapping {
  id_field?: string;
  text_field?: string;
  title_field?: string;
  type_field?: string;
  timestamp_field?: string;
  metadata_fields?: Record<string, string>;
}

export interface DataSourceConfig {
  id: string;
  name: string;
  source_type: string;
  status: "connected" | "error" | "disconnected";
  query_mode: "ingest" | "live" | "both";
  connection_string?: string;
  endpoint?: string;
  database?: string;
  table_or_query?: string;
  field_mapping?: FieldMapping;
  doc_count?: number;
  error_message?: string;
  created_at?: string;
}

export interface DataSourceType {
  id: string;
  name: string;
  description: string;
  supports_live: boolean;
  auth_methods: string[];
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
}

// ── Pipelines ──

export interface PipelineStep {
  name: string;
  capability: string;
  params: Record<string, unknown>;
}

export interface PipelineConfig {
  name: string;
  description: string;
  steps: PipelineStep[];
  source?: string;
}

export interface PipelineRun {
  id: string;
  pipeline_name: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at?: string;
  result?: Record<string, unknown>;
}

// ── Processing ──

export interface EntityResult {
  text: string;
  type: string;
  confidence: number;
}

export interface InsightsReport {
  summary: string;
  key_findings: string[];
  entities: EntityResult[];
  topics: string[];
}
