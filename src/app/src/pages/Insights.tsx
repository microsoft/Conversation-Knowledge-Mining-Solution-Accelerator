import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Dropdown,
  Field,
  Option,
  Spinner,
  Skeleton,
  SkeletonItem,
  Text,
  Tooltip,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import {
  Alert24Regular,
  ArrowSync24Regular,
  Board24Regular,
  ChartMultiple24Regular,
  ChevronDown20Regular,
  ChevronRight20Regular,
  ChevronUp20Regular,
  DocumentBulletList20Regular,
  Info24Regular,
  Link24Regular,
  Person24Regular,
  Sparkle24Regular,
} from "@fluentui/react-icons";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bar,
  BarChart as RBarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as ReTooltip,
  XAxis,
  YAxis,
} from "recharts";

import { getDashboard } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import type { AiLayoutBlock, DashboardResponse, InsightRuntime, RuntimeInsight } from "../types/api";

const PALETTE = [
  "#2563eb",
  "#0f766e",
  "#7c3aed",
  "#f59e0b",
  "#dc2626",
  "#0891b2",
  "#65a30d",
  "#ea580c",
  "#6366f1",
  "#14b8a6",
];

const useStyles = makeStyles({
  page: {
    minHeight: "100%",
    padding: "24px",
    boxSizing: "border-box",
    background:
      "radial-gradient(circle at top left, rgba(37, 99, 235, 0.08), transparent 35%), linear-gradient(180deg, #f8fafc 0%, #ffffff 100%)",
  },
  shell: {
    maxWidth: "1400px",
    margin: "0 auto",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  heroCard: {
    borderRadius: "18px",
    boxShadow: "0 18px 50px rgba(15, 23, 42, 0.08)",
    background: "linear-gradient(135deg, #ffffff 0%, #eff6ff 100%)",
  },
  heroBody: {
    padding: "22px",
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  heroTop: {
    display: "flex",
    justifyContent: "space-between",
    gap: "16px",
    flexWrap: "wrap",
    alignItems: "flex-start",
  },
  title: {
    fontSize: "30px",
    lineHeight: 1.1,
    fontWeight: 700,
    letterSpacing: "-0.03em",
    color: tokens.colorNeutralForeground1,
    marginTop: "8px",
  },
  heroMeta: {
    display: "flex",
    flexWrap: "wrap",
    gap: "10px 14px",
    marginTop: "10px",
    color: tokens.colorNeutralForeground3,
  },
  signalRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  filtersCard: {
    borderRadius: "14px",
    border: "1px solid #dbeafe",
    background: "rgba(255, 255, 255, 0.85)",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  filterHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "10px",
    flexWrap: "wrap",
  },
  filterGroups: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    gap: "10px",
  },
  refreshHint: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    background: "#eef6ff",
    border: "1px solid #bfdbfe",
    borderRadius: "10px",
    padding: "8px 10px",
    color: "#1d4ed8",
  },
  filterGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  filterValues: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  sectionCard: {
    borderRadius: "18px",
    boxShadow: "0 12px 30px rgba(15, 23, 42, 0.06)",
    overflow: "hidden",
  },
  sectionBody: {
    padding: "0 20px 22px",
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  sectionHeader: {
    display: "flex",
    alignItems: "baseline",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
  },
  sectionEyebrow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    color: tokens.colorNeutralForeground3,
  },
  overviewGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: "16px",
  },
  metricCard: {
    borderRadius: "16px",
    boxShadow: "0 10px 24px rgba(15, 23, 42, 0.06)",
    minHeight: "116px",
  },
  metricValue: {
    fontSize: "32px",
    lineHeight: 1,
    fontWeight: 700,
    letterSpacing: "-0.03em",
  },
  metricSubtext: {
    fontSize: "12px",
    color: tokens.colorNeutralForeground3,
  },
  discoveryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))",
    gap: "10px",
  },
  discoveryButton: {
    justifyContent: "flex-start",
    minHeight: "56px",
    padding: "12px 14px",
    textAlign: "left",
    whiteSpace: "normal",
    lineHeight: 1.4,
  },
  insightGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "14px",
  },
  insightCard: {
    borderRadius: "16px",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.05)",
  },
  insightBody: {
    padding: "0 16px 16px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  severityRow: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap",
  },
  distributionGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
    gap: "12px",
  },
  distributionStack: {
    display: "grid",
    gridTemplateColumns: "1fr",
    gap: "16px",
  },
  topicList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    maxHeight: "420px",
    overflowY: "auto",
    paddingRight: "4px",
  },
  topicItem: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  topicHead: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
  },
  topicName: {
    minWidth: 0,
    flex: 1,
    fontSize: "13px",
    fontWeight: 600,
    color: tokens.colorNeutralForeground1,
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  barTrack: {
    height: "10px",
    borderRadius: "999px",
    backgroundColor: tokens.colorNeutralStroke2,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: "999px",
  },
  barCard: {
    borderRadius: "14px",
    padding: "14px 16px",
    background: "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
    border: "1px solid #e2e8f0",
  },
  barLabel: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    marginBottom: "8px",
  },
  evidenceCard: {
    borderRadius: "14px",
  },
  tipCard: {
    borderRadius: "18px",
    background: "linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%)",
  },
  errorCard: {
    borderRadius: "18px",
  },
  noticeCard: {
    borderRadius: "14px",
    border: "1px solid #bfdbfe",
    background: "#f8fbff",
  },
  aiFirstGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
    gap: "14px",
  },
  findingsHeaderRow: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: "12px",
    flexWrap: "wrap",
  },
  scorePill: {
    borderRadius: "999px",
    padding: "2px 8px",
    fontSize: "12px",
    fontWeight: 700,
    background: "#e0ecff",
    color: "#1d4ed8",
  },
  tagRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
  },
  explainBox: {
    borderRadius: "10px",
    border: "1px solid #dbeafe",
    background: "#f8fbff",
    padding: "8px 10px",
  },
  relationshipStrengthRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  relationshipStrengthTrack: {
    flex: 1,
    height: "8px",
    borderRadius: "999px",
    background: "#e2e8f0",
    overflow: "hidden",
  },
  relationshipStrengthFill: {
    height: "100%",
    borderRadius: "999px",
    background: "linear-gradient(90deg, #2563eb 0%, #14b8a6 100%)",
  },
  timelineList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  timelineItem: {
    display: "grid",
    gridTemplateColumns: "14px 1fr",
    gap: "10px",
    alignItems: "start",
  },
  timelineDot: {
    width: "10px",
    height: "10px",
    borderRadius: "999px",
    marginTop: "5px",
    background: "#2563eb",
  },
});

const TEST_PATTERN = /^(test_?doc|sample_?|tmp_?|e2e_?|large_docx|fake_?|mock_?|__)/i;
const JUNK_LABELS = new Set(["docx", "lorem ipsum", "lorem", "ipsum", "placeholder", "n/a", "null", "undefined", "none"]);
const DATE_LIKE_PATTERN = /^(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z?)$/i;
const DATE_LIKE_NORMALIZED_PATTERN = /^\d{4}\s\d{1,2}\s\d{1,2}$/;
const NOISE_ENTITY_TERMS = new Set([
  "issue",
  "issues",
  "unknown",
  "other",
  "misc",
  "miscellaneous",
  "n/a",
  "na",
  "none",
  "null",
  "undefined",
]);
const GENERIC_CONNECTION_FROM = new Set(["topic", "mined topic", "sentiment", "complaint", "category", "type", "status", "outcome"]);
const LOW_SIGNAL_TOPICS = new Set([
  "important", "includes", "cover", "covered", "contact", "other", "ensure", "understand",
  "provide", "services", "information", "necessary",
]);
const FILTER_BLOCKLIST = new Set(["page_count", "pagecount", "pages", "page"]);

const isTestLabel = (value: string) => {
  const lower = (value || "").trim().toLowerCase();
  return TEST_PATTERN.test(lower) || JUNK_LABELS.has(lower);
};

const cleanItems = <T extends { label?: string; name?: string; text?: string }>(items: T[]): T[] =>
  items.filter((item) => !isTestLabel(String(item.label ?? item.name ?? item.text ?? "")));

const cleanEntityLabel = (raw: string) => {
  const value = String(raw || "").trim();
  if (!value) return "";
  if (value.includes("->")) return value.split("->")[0].trim();
  return value;
};

const normalizeDisplayLabel = (raw: string) =>
  String(raw || "")
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const isLikelyEntityLabel = (raw: string) => {
  const value = normalizeDisplayLabel(cleanEntityLabel(raw));
  const lower = value.toLowerCase();
  if (!value || value.length < 3) return false;
  if (isTestLabel(value)) return false;
  if (DATE_LIKE_PATTERN.test(value)) return false;
  if (DATE_LIKE_NORMALIZED_PATTERN.test(value)) return false;
  if (/^\d+$/.test(value)) return false;
  if (NOISE_ENTITY_TERMS.has(lower)) return false;
  return true;
};

const fmtKpi = (kpi: { value?: number | string; format?: string }) => {
  if (kpi.format === "percentage") return `${kpi.value}%`;
  if (kpi.format === "minutes") return `${kpi.value}m`;
  if (kpi.format === "currency") return `$${Number(kpi.value).toLocaleString()}`;
  return String(kpi.value ?? "—");
};

const formatDate = (value?: string) => {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString();
};

const toArray = <T,>(value: unknown): T[] => (Array.isArray(value) ? value : []);

const toRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;

const pickLabel = (row: Record<string, unknown>): string => {
  const direct = ["label", "text", "name", "title", "value_label", "dimension", "category"];
  for (const key of direct) {
    const value = row[key];
    if (typeof value === "string" && value.trim()) return value.trim();
  }

  for (const [key, value] of Object.entries(row)) {
    if (/(id|uuid|guid|count|total|value|score|rate|percent|weight|frequency)/i.test(key)) continue;
    if (typeof value === "string" && value.trim()) return value.trim();
  }

  return "";
};

const pickValue = (row: Record<string, unknown>): number => {
  const direct = ["value", "frequency", "count", "total", "mentions", "score", "weight", "rate", "positive", "sample_size"];
  for (const key of direct) {
    const raw = row[key];
    const value = typeof raw === "number" ? raw : Number(raw);
    if (Number.isFinite(value)) return value;
  }
  return 0;
};

const getChartRows = (chart: Record<string, unknown>): Record<string, unknown>[] => {
  const payload = chart.data;
  if (Array.isArray(payload)) {
    return payload.filter((row): row is Record<string, unknown> => Boolean(toRecord(row)));
  }

  const obj = toRecord(payload);
  if (!obj) return [];

  const nested = ["rows", "items", "values", "data"];
  for (const key of nested) {
    const value = obj[key];
    if (Array.isArray(value)) {
      return value.filter((row): row is Record<string, unknown> => Boolean(toRecord(row)));
    }
  }

  return [];
};

const deriveRuntimeFromDashboard = (dashboard: DashboardResponse): InsightRuntime => {
  const topicsMap = new Map<string, number>();
  const entitiesMap = new Map<string, number>();
  const relationships: Array<{ from: string; to: string; relation?: string; strength: number }> = [];

  toArray<unknown>(dashboard.sections).forEach((sectionValue) => {
    const section = toRecord(sectionValue);
    if (!section) return;

    toArray<unknown>(section.charts).forEach((chartValue) => {
      const chart = toRecord(chartValue);
      if (!chart) return;

      const viz = String(chart.visualization || "").toLowerCase();
      const title = String(chart.title || "").toLowerCase();
      const field = String(chart.field || "").toLowerCase();
      const insightType = String(chart.insight_type || "").toLowerCase();
      const isTopicLike =
        viz === "word_cloud" ||
        /topic|theme|phrase|keyword/.test(title) ||
        /topic|theme|phrase|keyword/.test(field);

      getChartRows(chart).forEach((row) => {
        if (viz === "word_cloud") {
          const label = pickLabel(row);
          const value = Number(row.frequency ?? row.weight ?? row.value ?? 0) || 0;
          if (label && value > 0) {
            topicsMap.set(label, (topicsMap.get(label) || 0) + value);
          }
          return;
        }

        const rawLabel = pickLabel(row);
        const label = cleanEntityLabel(rawLabel);
        const value = pickValue(row);
        if (!label || value <= 0) return;

        if (isTopicLike) {
          topicsMap.set(label, (topicsMap.get(label) || 0) + value);
        } else {
          entitiesMap.set(label, (entitiesMap.get(label) || 0) + value);
        }
      });

      if (viz === "driver_table" || insightType === "drivers") {
        const payload = toRecord(chart.data);
        const outcome = String(payload?.outcome_label || "Outcome");
        toArray<unknown>(payload?.factors).forEach((factorValue) => {
          const factor = toRecord(factorValue);
          if (!factor) return;
          const from = String(factor.dimension || "").trim();
          const to = String(factor.value || "").trim();
          const strength = Math.abs(Number(factor.deviation ?? 0)) || 0;
          if (from && to) {
            relationships.push({ from, to, relation: `affects ${outcome}`, strength });
          }
        });
      }
    });
  });

  const topics = Array.from(topicsMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([name, score], index) => ({
      id: `topic_${index + 1}`,
      name,
      score,
      trendDirection: "stable" as const,
      trendValue: null,
    }));

  const entities = Array.from(entitiesMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 30)
    .map(([name, mentions], index) => ({
      id: `entity_${index + 1}`,
      name,
      mentions: Math.round(mentions),
      trendDirection: "stable" as const,
      trendValue: null,
    }));

  const classify = (text: string): RuntimeInsight["category"] => {
    const lower = text.toLowerCase();
    if (lower.includes("risk") || lower.includes("concern")) return "Risk";
    if (lower.includes("anomaly") || lower.includes("unusual") || lower.includes("spike") || lower.includes("drop")) return "Anomaly";
    if (lower.includes("opportun") || lower.includes("potential")) return "Opportunity";
    if (lower.includes("trend") || lower.includes("increase") || lower.includes("decrease")) return "Trend";
    return "Insight";
  };

  const insights = [...toArray<unknown>(dashboard.key_insights), ...toArray<unknown>(dashboard.standout_findings)]
    .filter((item) => typeof item === "string" && item.trim())
    .map((title, index) => ({
      id: `insight_${index + 1}`,
      category: classify(String(title)),
      title: String(title),
      confidence: null,
      impactScore: 0.75,
      context: dashboard.headline,
      explanation: dashboard.summary,
      evidenceCount: 0,
      evidence: [],
    }));

  const unexpectedPatterns = toArray<unknown>(dashboard.standout_findings)
    .filter((item) => typeof item === "string" && item.trim())
    .slice(0, 6)
    .map((pattern, index) => ({
      id: `pattern_${index + 1}`,
      pattern: String(pattern),
      severity: /(risk|anomaly|critical|spike|drop)/i.test(String(pattern)) ? ("high" as const) : ("medium" as const),
      explanation: dashboard.summary || "Observed in the analyzed records.",
    }));

  const actions = toArray<unknown>(dashboard.suggested_questions)
    .filter((item) => typeof item === "string" && item.trim())
    .map((label, index) => ({ id: `action_${index + 1}`, label: String(label), intentType: "explore" }));

  return {
    schemaVersion: "1.0",
    generatedAt: new Date().toISOString(),
    recordCount: dashboard.data_context?.filtered_records || dashboard.data_context?.total_records || 0,
    counts: {
      topics: topics.length,
      entities: entities.length,
      relationships: relationships.length,
    },
    summarySignals: [dashboard.headline, ...toArray<unknown>(dashboard.key_insights)]
      .filter((item) => typeof item === "string" && item.trim())
      .map((item) => String(item))
      .slice(0, 6),
    kpis: toArray<any>(dashboard.kpis).map((kpi, index) => ({
      id: `kpi_${index + 1}`,
      label: String(kpi.label || `KPI ${index + 1}`),
      value: kpi.value,
      format: kpi.format,
      trendDirection: (kpi.trend === "up" ? "up" : kpi.trend === "down" ? "down" : "stable") as "up" | "down" | "stable",
      trendValue: null,
      confidence: null,
    })),
    topics,
    entities,
    relationships,
    insights,
    unexpectedPatterns,
    actions,
  };
};

const mergeRuntimeData = (
  primary: InsightRuntime | null | undefined,
  fallback: InsightRuntime | null | undefined,
): InsightRuntime | null => {
  if (!primary && !fallback) return null;
  if (!primary) return fallback || null;
  if (!fallback) return primary;

  const prefer = <T,>(first: T[] | undefined, second: T[] | undefined): T[] => {
    const firstItems = Array.isArray(first) ? first : [];
    const secondItems = Array.isArray(second) ? second : [];
    return firstItems.length > 0 ? firstItems : secondItems;
  };

  const topics = prefer(primary.topics, fallback.topics);
  const entities = prefer(primary.entities, fallback.entities);
  const relationships = prefer(primary.relationships, fallback.relationships);
  const insights = prefer(primary.insights, fallback.insights);
  const unexpectedPatterns = prefer(primary.unexpectedPatterns, fallback.unexpectedPatterns);
  const kpis = prefer(primary.kpis, fallback.kpis);
  const actions = prefer(primary.actions, fallback.actions);
  const summarySignals = prefer(primary.summarySignals, fallback.summarySignals);

  return {
    ...primary,
    recordCount: primary.recordCount || fallback.recordCount || 0,
    generatedAt: primary.generatedAt || fallback.generatedAt || new Date().toISOString(),
    topics,
    entities,
    relationships,
    insights,
    unexpectedPatterns,
    kpis,
    actions,
    summarySignals,
    counts: {
      topics: topics.length,
      entities: entities.length,
      relationships: relationships.length,
    },
  };
};

const SkeletonDashboard: React.FC = () => {
  const styles = useStyles();

  return (
    <Skeleton aria-label="Loading dashboard">
      <div className={styles.page}>
        <Card className={styles.heroCard}>
          <div className={styles.heroBody}>
            <SkeletonItem shape="rectangle" size={20} style={{ width: 220, height: 20 }} />
            <SkeletonItem shape="rectangle" size={32} style={{ width: "45%", height: 32 }} />
            <div className={styles.signalRow}>
              {[120, 140, 110, 150].map((width, index) => (
                <SkeletonItem key={index} shape="rectangle" size={28} style={{ width, borderRadius: 999 }} />
              ))}
            </div>
          </div>
        </Card>
        <div className={styles.overviewGrid}>
          {[1, 2, 3, 4].map((index) => (
            <Card key={index} className={styles.metricCard}>
              <SkeletonItem shape="rectangle" size={28} style={{ width: 68, marginBottom: 10 }} />
              <SkeletonItem shape="rectangle" size={12} style={{ width: 120 }} />
            </Card>
          ))}
        </div>
      </div>
    </Skeleton>
  );
};

const getSeverityStyle = (severity: string) => {

  if (severity === "Critical") return { badge: "danger" as const, accent: "#dc2626", text: "#7f1d1d", border: "#fecaca", bg: "#fff" };
  if (severity === "High") return { badge: "warning" as const, accent: "#ea580c", text: "#7c2d12", border: "#fed7aa", bg: "#fff" };
  if (severity === "Risk") return { badge: "danger" as const, accent: "#dc2626", text: "#991b1b", border: "#fecaca", bg: "#fff" };
  if (severity === "Opportunity") return { badge: "success" as const, accent: "#16a34a", text: "#166534", border: "#86efac", bg: "#fff" };
  if (severity === "Trend") return { badge: "brand" as const, accent: "#2563eb", text: "#1d4ed8", border: "#93c5fd", bg: "#fff" };
  return { badge: "brand" as const, accent: "#2563eb", text: "#1d4ed8", border: "#bfdbfe", bg: "#fff" };
};

const TAG_STOPWORDS = new Set(["the", "and", "with", "from", "this", "that", "were", "have", "into", "across", "about", "records", "record", "analysis"]);

const buildAiTags = (...texts: string[]): string[] => {
  const bag = new Map<string, number>();
  const tokenRe = /[A-Za-z][A-Za-z0-9_-]{3,}/g;
  texts.forEach((text) => {
    for (const match of String(text || "").toLowerCase().matchAll(tokenRe)) {
      const token = match[0];
      if (TAG_STOPWORDS.has(token)) continue;
      bag.set(token, (bag.get(token) || 0) + 1);
    }
  });
  return Array.from(bag.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([token]) => token.replace(/_/g, " "));
};

const toConversationalPrompt = (value: string) => {
  const text = String(value || "").trim();
  if (!text) return "Ask what changed in this dataset.";
  if (/[?]$/.test(text)) return text;
  return `Can you help me explore: ${text}?`;
};

const dedupeNarrative = (text: string, compared: string[]) => {
  const normalized = String(text || "").trim().toLowerCase();
  if (!normalized) return "";
  const repeated = compared.some((item) => String(item || "").trim().toLowerCase() === normalized);
  return repeated ? "" : String(text || "").trim();
};

const NARRATIVE_STOPWORDS = new Set([
  "windows", "laptop", "printer", "scanner", "wifi", "network", "helpdesk", "support", "service", "team",
]);

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

const inferOrganizationLabel = (texts: string[]) => {
  const corpus = texts.join("\n");
  if (/\bWoodgrove IT Helpdesk\b/i.test(corpus)) return "Woodgrove IT Helpdesk";

  const matches = Array.from(
    corpus.matchAll(/([A-Z][A-Za-z0-9&-]*(?:\s+[A-Z][A-Za-z0-9&-]*){0,5}\s+(?:Helpdesk|Service|Department|Center|Desk|Support))/g),
  ).map((m) => m[1].trim());

  if (matches.length === 0) return "the organization";
  const ranked = matches.sort((a, b) => b.length - a.length);
  const best = ranked[0];
  if (/^IT Support$/i.test(best)) return "the organization";
  return best;
};

const extractLikelyPersonNames = (texts: string[], orgLabel: string): string[] => {
  const corpus = texts.join("\n");
  const candidates = new Set<string>();

  for (const match of corpus.matchAll(/\b([A-Z][a-z]{2,})'s\b/g)) {
    candidates.add(match[1]);
  }
  for (const match of corpus.matchAll(/\bby\s+([A-Z][a-z]{2,})\b/g)) {
    candidates.add(match[1]);
  }
  for (const match of corpus.matchAll(/\b([A-Z][a-z]{2,})\s+(?:frequently|consistently|contacted|requested|reported|expressed|raised|experienced)\b/g)) {
    candidates.add(match[1]);
  }

  const orgWords = new Set((orgLabel.match(/\b[A-Za-z]{3,}\b/g) || []));
  return Array.from(candidates).filter((token) => {
    const low = token.toLowerCase();
    return !NARRATIVE_STOPWORDS.has(low) && !orgWords.has(token);
  });
};

const sanitizeNarrative = (text: string, names: string[], orgLabel: string): string => {
  let sanitized = text;
  for (const name of names) {
    const escaped = escapeRegExp(name);
    sanitized = sanitized.replace(new RegExp(`\\b${escaped}['’]s\\b`, "g"), `${orgLabel}'s`);
    sanitized = sanitized.replace(new RegExp(`\\b${escaped}\\b`, "g"), "users");
  }
  sanitized = sanitized.replace(
    new RegExp(`\\b${escapeRegExp(orgLabel)}['’]s interactions? with (?:the )?${escapeRegExp(orgLabel)}\\b`, "gi"),
    `${orgLabel} support interactions`,
  );
  sanitized = sanitized.replace(
    new RegExp(`\\b${escapeRegExp(orgLabel)}['’]s\\s+IT Support\\b`, "gi"),
    `${orgLabel} Support`,
  );
  sanitized = sanitized.replace(/\bIT Support['’]s\s+IT Support\b/gi, `${orgLabel} Support`);
  sanitized = sanitized.replace(
    /\bIT Support['’]s interactions? with (?:the )?Woodgrove IT Helpdesk\b/gi,
    "Woodgrove IT Helpdesk support interactions",
  );
  return sanitized.replace(/\s+/g, " ").trim();
};

const sanitizeDashboardNarrative = (payload: DashboardResponse): DashboardResponse => {
  const texts = [
    payload.headline || "",
    payload.summary || "",
    ...(payload.key_insights || []),
    ...(payload.standout_findings || []),
  ].filter((v): v is string => typeof v === "string" && v.trim().length > 0);

  const orgLabel = inferOrganizationLabel(texts);
  const names = extractLikelyPersonNames(texts, orgLabel);

  return {
    ...payload,
    headline: sanitizeNarrative(payload.headline || "", names, orgLabel),
    summary: sanitizeNarrative(payload.summary || "", names, orgLabel),
    key_insights: (payload.key_insights || []).map((item) => sanitizeNarrative(item, names, orgLabel)),
    standout_findings: (payload.standout_findings || []).map((item) => sanitizeNarrative(item, names, orgLabel)),
    suggested_questions: (payload.suggested_questions || []).map((item) => sanitizeNarrative(item, names, orgLabel)),
  };
};

const Insights: React.FC = () => {
  const styles = useStyles();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const { setDashboardHeadline, insights: cachedData, setInsights } = useAppState();
  const initialSourceFilter = searchParams.get("source") || "";

  const [data, setData] = useState<DashboardResponse | null>(cachedData);
  const [loading, setLoading] = useState(!cachedData);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>(() => ({
    ...(cachedData?.data_context?.filters_applied || {}),
    ...(initialSourceFilter ? { source: initialSourceFilter } : {}),
  }));
  const [showMoreOverview, setShowMoreOverview] = useState(false);
  const [expandedFindings, setExpandedFindings] = useState<Set<string>>(new Set());

  const load = useCallback(async (filterValues?: Record<string, string>, refresh = false) => {
    if (refresh) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const response = await getDashboard(filterValues, refresh);
      const sanitized = sanitizeDashboardNarrative(response.data);
      setData(sanitized);
      setInsights(sanitized);
      if (sanitized?.headline) setDashboardHeadline(sanitized.headline);
    } catch {
      setError("Failed to load dashboard. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [setDashboardHeadline, setInsights]);

  useEffect(() => {
    if (cachedData) {
      const sanitizedCached = sanitizeDashboardNarrative(cachedData);
      if (JSON.stringify(sanitizedCached) !== JSON.stringify(cachedData)) {
        setData(sanitizedCached);
        setInsights(sanitizedCached);
        if (sanitizedCached?.headline) setDashboardHeadline(sanitizedCached.headline);
      }
    }

    if (!cachedData || !cachedData.runtime) {
      load(initialSourceFilter ? { source: initialSourceFilter } : undefined);
    }
  }, [cachedData, initialSourceFilter, load, setDashboardHeadline, setInsights]);

  const runtime = useMemo(() => {
    const primary = data?.runtime ?? null;
    const fallback = data ? deriveRuntimeFromDashboard(data) : null;
    return mergeRuntimeData(primary, fallback);
  }, [data]);
  const dataset = data?.datasetInfo || { name: "Dataset", sourceType: "documents", lastUpdated: new Date().toISOString() };
  const availableFilters = useMemo(
    () => (data?.filters || []).filter((filter: any) => {
      const key = String(filter?.field || filter?.label || "").toLowerCase().replace(/\s+/g, "_");
      return !FILTER_BLOCKLIST.has(key);
    }),
    [data]
  );

  const metrics = useMemo(() => {
    const topicsCount = runtime?.counts?.topics || runtime?.topics?.length || 0;
    const entitiesCount = runtime?.counts?.entities || runtime?.entities?.length || 0;
    const relationshipsCount = runtime?.counts?.relationships || runtime?.relationships?.length || 0;
    const insightsCount = runtime?.insights?.length || 0;
    const anomaliesCount = runtime?.unexpectedPatterns?.length || 0;
    const sectionsCount = data?.sections?.length || 0;
    const questionsCount = data?.suggested_questions?.length || 0;
    const findingsCount = data?.standout_findings?.length || 0;

    return {
      processed: data?.data_context?.filtered_records || data?.data_context?.total_records || "—",
      topicsCount,
      entitiesCount,
      relationshipsCount,
      insightsCount,
      anomaliesCount,
      sectionsCount,
      questionsCount,
      findingsCount,
      kpiCount: runtime?.kpis?.length || 0,
    };
  }, [data, runtime]);

  const aiLayoutBlocks = useMemo((): AiLayoutBlock[] => {
    const raw = (data as DashboardResponse & { ai_layout?: unknown })?.ai_layout;
    if (!Array.isArray(raw)) return [];
    return raw.filter(
      (item): item is AiLayoutBlock => Boolean(item && typeof item === "object" && typeof (item as AiLayoutBlock).type === "string")
    );
  }, [data]);

  const chartEvidence = useMemo(() => {
    const evidence: string[] = [];
    (data?.sections || []).forEach((section: any) => {
      (section?.charts || []).forEach((chart: any) => {
        const title = String(chart?.title || "").trim();
        const description = String(chart?.description || "").trim();
        if (title) evidence.push(title);
        if (description) evidence.push(description);
      });
    });
    return evidence.slice(0, 12);
  }, [data]);

  const rankedInsights = useMemo(() => {
    const runtimeInsights = ((runtime?.insights || []) as any[])
      .filter((insight) => typeof insight?.title === "string" && insight.title.trim().length > 0)
      .filter((insight) => !isTestLabel(String(insight.title)));

    const fallbackInsights = [
      ...(data?.key_insights || []).map((title, index) => ({
        id: `key_${index + 1}`,
        title,
        category: "Insight",
        confidence: null,
        context: "Derived from key insights.",
        explanation: null,
        evidence: [],
      })),
      ...(data?.standout_findings || []).map((title, index) => ({
        id: `finding_${index + 1}`,
        title,
        category: "Finding",
        confidence: null,
        context: "Derived from standout findings.",
        explanation: null,
        evidence: [],
      })),
    ];

    const source = runtimeInsights.length > 0 ? runtimeInsights : fallbackInsights;

    const toSeverity = (category: string) => {
      const lower = String(category || "").toLowerCase();
      if (lower.includes("critical") || lower.includes("anomaly")) return "Critical";
      if (lower.includes("risk")) return "Risk";
      if (lower.includes("opportun")) return "Opportunity";
      if (lower.includes("trend")) return "Trend";
      return "Insight";
    };

    const toScore = (insight: any, severity: string) => {
      const severityWeight: Record<string, number> = {
        Critical: 1,
        Risk: 0.85,
        Opportunity: 0.7,
        Trend: 0.55,
        Insight: 0.45,
      };
      const confidence = typeof insight.confidence === "number" ? insight.confidence : 0.55;
      const impact = typeof insight.impactScore === "number" ? insight.impactScore : 0.6;
      const evidenceCount = Array.isArray(insight.evidence) ? insight.evidence.length : Number(insight.evidenceCount || 0);
      const evidenceBoost = Math.min(evidenceCount / 8, 0.2);
      const score = (severityWeight[severity] || 0.4) * 0.5 + confidence * 0.25 + impact * 0.25 + evidenceBoost;
      return Math.round(score * 100);
    };

    return source
      .map((insight) => ({
        ...insight,
        severity: toSeverity(insight.category),
        confidence: typeof insight.confidence === "number" ? insight.confidence : null,
        aiTags: buildAiTags(String(insight.title || ""), String(insight.context || ""), String(insight.explanation || "")),
        score: toScore(insight, toSeverity(insight.category)),
        explanation: dedupeNarrative(String(insight.explanation || ""), [String(insight.title || ""), String(insight.context || "")]),
      }))
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 6);
  }, [runtime, data]);

  const hasSparseSignal = useMemo(() => {
    return metrics.topicsCount === 0 && metrics.entitiesCount === 0 && rankedInsights.length <= 1;
  }, [metrics.topicsCount, metrics.entitiesCount, rankedInsights.length]);

  const aiTimeline = useMemo(() => {
    if ((runtime?.events || []).length > 0) {
      return (runtime?.events || []).slice(0, 8).map((event, index) => ({
        id: `evt_${index + 1}`,
        marker: event.date || `Step ${index + 1}`,
        title: event.event,
        description: event.change,
      }));
    }

    return (runtime?.unexpectedPatterns || []).slice(0, 6).map((item, index) => ({
      id: item.id || `pattern_${index + 1}`,
      marker: `Pattern ${index + 1}`,
      title: item.pattern,
      description: item.explanation,
    }));
  }, [runtime]);

  const topicBars = useMemo(() => (runtime?.topics || [])
    .filter((topic) => !isTestLabel(topic.name))
    .filter((topic) => !LOW_SIGNAL_TOPICS.has(String(topic.name || "").toLowerCase().trim()))
    .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 8)
    .map((topic, index) => ({
      name: topic.name,
      score: Math.max(Number(topic.score || 0), 0),
      fill: PALETTE[index % PALETTE.length],
    })), [runtime]);

  const entityBars = useMemo(() => {
    const merged = new Map<string, number>();
    (runtime?.entities || []).forEach((entity) => {
      const name = normalizeDisplayLabel(entity.name);
      const mentions = Math.max(Number(entity.mentions || 0), 0);
      if (!isLikelyEntityLabel(name) || mentions <= 0) return;
      merged.set(name, (merged.get(name) || 0) + mentions);
    });

    return Array.from(merged.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 8)
      .map(([name, mentions], index) => ({
        name,
        mentions,
        fill: PALETTE[(index + 2) % PALETTE.length],
      }));
  }, [runtime]);

  const topicShareBars = useMemo(() => {
    const total = topicBars.reduce((sum, item) => sum + item.score, 0);
    return topicBars.map((item) => ({
      ...item,
      share: total > 0 ? (item.score / total) * 100 : 0,
    }));
  }, [topicBars]);

  const relationships = useMemo(() => {
    const merged = new Map<string, { from: string; to: string; relation: string; strength: number; count: number }>();
    const highSignal = new Set<string>([
      ...topicBars.slice(0, 12).map((item) => item.name.toLowerCase()),
      ...entityBars.slice(0, 12).map((item) => item.name.toLowerCase()),
    ]);

    (runtime?.relationships || []).forEach((relationship) => {
      const from = normalizeDisplayLabel(relationship.from || "");
      const to = normalizeDisplayLabel(relationship.to || "");
      const relation = normalizeDisplayLabel(relationship.relation || "related");
      const strength = Math.max(Number(relationship.strength || 0), 0);
      const fromLower = from.toLowerCase();
      const toLower = to.toLowerCase();

      if (!isLikelyEntityLabel(from) || !isLikelyEntityLabel(to)) return;
      if (fromLower === toLower) return;
      if (strength <= 0) return;
      if (GENERIC_CONNECTION_FROM.has(fromLower) && !highSignal.has(fromLower)) return;
      if (highSignal.size > 0 && !highSignal.has(fromLower) && !highSignal.has(toLower)) return;

      const key = `${fromLower}|${relation.toLowerCase()}|${toLower}`;
      const existing = merged.get(key);
      if (!existing) {
        merged.set(key, { from, to, relation, strength, count: 1 });
      } else {
        existing.strength = Math.max(existing.strength, strength);
        existing.count += 1;
      }
    });

    const ranked = Array.from(merged.values())
      .sort((a, b) => {
        if (b.strength !== a.strength) return b.strength - a.strength;
        return b.count - a.count;
      });

    const picked: Array<{ from: string; to: string; relation: string; strength: number }> = [];
    const seenFrom = new Set<string>();
    for (const item of ranked) {
      if (picked.length >= 5) break;
      if (seenFrom.has(item.from.toLowerCase()) && picked.length < 3) continue;
      picked.push({ from: item.from, to: item.to, relation: item.relation, strength: item.strength });
      seenFrom.add(item.from.toLowerCase());
    }

    return picked;
  }, [runtime, topicBars, entityBars]);

  const hasConnectionStrengthVariance = useMemo(() => {
    if (relationships.length <= 1) return false;
    const first = relationships[0]?.strength || 0;
    return relationships.some((item) => Math.abs((item.strength || 0) - first) > 0.01);
  }, [relationships]);

  const maxRelationshipStrength = useMemo(() => {
    return Math.max(1, ...relationships.map((item) => Number(item.strength || 0)));
  }, [relationships]);

  const toggleFinding = useCallback((id: string) => {
    setExpandedFindings((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const rankedKpis = useMemo(() => {
    return [...(runtime?.kpis || [])]
      .map((kpi) => ({
        ...kpi,
        numericValue: Number(kpi.value),
      }))
      .sort((a, b) => {
        const left = Number.isFinite(a.numericValue) ? Math.abs(a.numericValue) : -1;
        const right = Number.isFinite(b.numericValue) ? Math.abs(b.numericValue) : -1;
        return right - left;
      })
      .slice(0, 8);
  }, [runtime]);

  const moreMetrics = [
    { label: "Key insights", value: metrics.insightsCount, summary: "How many key insights were returned for this dataset.", color: PALETTE[4] },
    { label: "Standout findings", value: metrics.findingsCount, summary: "How many standout findings were highlighted.", color: PALETTE[5] },
    { label: "Analysis sections", value: metrics.sectionsCount, summary: "How many analysis blocks were generated.", color: PALETTE[6] },
    { label: "Suggested questions", value: metrics.questionsCount, summary: "Suggested follow-up questions you can ask next.", color: PALETTE[7] },
    { label: "KPI metrics", value: metrics.kpiCount, summary: "Number of KPI values currently shown.", color: PALETTE[0] },
    { label: "Flagged patterns", value: metrics.anomaliesCount, summary: "Potential outliers or unusual patterns detected.", color: PALETTE[3] },
  ];

  const setFilterValue = useCallback((field: string, value?: string) => {
    const next = { ...filters };
    const normalized = (value || "").trim();
    if (!normalized) {
      delete next[field];
    } else {
      next[field] = normalized;
    }
    setFilters(next);
    void load(next);
  }, [filters, load]);

  const clearAllFilters = useCallback(() => {
    setFilters({});
    void load({});
  }, [load]);

  if (loading) return <SkeletonDashboard />;

  if (error) {
    return (
      <div className={styles.page}>
        <Card className={styles.errorCard}>
          <Text weight="semibold" size={500}>Unable to load Insights</Text>
          <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: "block", marginTop: 8 }}>{error}</Text>
        </Card>
      </div>
    );
  }

  if (!data) {
    return (
      <div className={styles.page}>
        <Card className={styles.errorCard}>
          <Text>No data available.</Text>
        </Card>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.shell}>
        <Card className={styles.heroCard}>
          <div className={styles.heroBody}>
            <div className={styles.heroTop}>
              <div>
                <div className={styles.sectionEyebrow}>
                  <Sparkle24Regular />
                  <Text weight="semibold" size={200}>Insights overview</Text>
                </div>
                <Text as="h1" className={styles.title}>{data?.headline || "Document insights dashboard"}</Text>
                <div className={styles.heroMeta}>
                  <Text size={200}>Dataset: {dataset?.name || "Dataset"}</Text>
                  <Text size={200}>Source: {dataset?.sourceType || "documents"}</Text>
                  <Text size={200}>Updated: {formatDate(dataset?.lastUpdated)}</Text>
                </div>
              </div>
              <Button
                appearance="secondary"
                icon={<ArrowSync24Regular />}
                onClick={() => load(filters, true)}
                disabled={refreshing}
              >
                {refreshing ? "Refreshing" : "Refresh"}
              </Button>
            </div>

            {availableFilters.length > 0 && (
              <div className={styles.filtersCard}>
                <div className={styles.filterHeader}>
                  <div className={styles.sectionEyebrow}>
                    <DocumentBulletList20Regular />
                    <Text weight="semibold" size={200}>Filter insights</Text>
                  </div>
                  <Button appearance="subtle" size="small" onClick={clearAllFilters} disabled={refreshing}>Clear all</Button>
                </div>

                {refreshing && (
                  <div className={styles.refreshHint}>
                    <Spinner size="tiny" />
                    <Text size={200} weight="semibold">Updating insights for selected filters...</Text>
                  </div>
                )}

                <div className={styles.filterGroups}>
                  {availableFilters.map((filter) => (
                    <div key={filter.field} className={styles.filterGroup}>
                      <Field size="small" label={filter.label || filter.field}>
                        <Dropdown
                          disabled={refreshing}
                          size="small"
                          value={filters[filter.field] || "All"}
                          selectedOptions={filters[filter.field] ? [filters[filter.field]] : [""]}
                          onOptionSelect={(_, data) => setFilterValue(filter.field, String(data.optionValue || ""))}
                        >
                          <Option value="">All</Option>
                          {(filter.values || []).map((value) => (
                            <Option key={`${filter.field}-${value}`} value={value}>
                              {value}
                            </Option>
                          ))}
                        </Dropdown>
                      </Field>
                    </div>
                  ))}
                </div>

              </div>
            )}
          </div>
        </Card>

        {aiLayoutBlocks.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>AI layout</Text>}
              description={<Text size={200}>Dynamic blocks chosen by the model for this dataset.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.aiFirstGrid}>
                {aiLayoutBlocks.map((block: AiLayoutBlock, index: number) => {
                  const type = block.type.toLowerCase();
                  const blockKey = `layout_${index}_${type}`;
                  if (type === "summary") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">Summary</Text>} description={<Text size={200}>{block.title || data.headline || "AI summary"}</Text>} />
                        <Text size={200} style={{ padding: "0 16px 16px", color: tokens.colorNeutralForeground3 }}>{block.text || data.summary || ""}</Text>
                      </Card>
                    );
                  }
                  if (type === "risk_card") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard} style={{ border: "1px solid #fecaca", background: "#fff1f2" }}>
                        <CardHeader header={<Text weight="semibold">Risk card</Text>} description={<Text size={200}>{block.title || "Potential risk"}</Text>} />
                        <Text size={200} style={{ padding: "0 16px 16px" }}>{block.description || data.summary || ""}</Text>
                      </Card>
                    );
                  }
                  if (type === "timeline") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">Timeline</Text>} />
                        <div className={styles.sectionBody}>
                          <div className={styles.timelineList}>
                            {aiTimeline.slice(0, 4).map((item) => (
                              <div key={item.id} className={styles.timelineItem}>
                                <div className={styles.timelineDot} />
                                <div>
                                  <Text weight="semibold" size={200}>{item.marker}</Text>
                                  <Text size={200} style={{ display: "block" }}>{item.title}</Text>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </Card>
                    );
                  }
                  if (type === "relationship_graph") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">Relationship graph</Text>} />
                        <div className={styles.sectionBody}>
                          {relationships.slice(0, 3).map((relationship, relIndex) => {
                            const pct = Math.min(100, (Number(relationship.strength || 0) / maxRelationshipStrength) * 100);
                            return (
                              <div key={`rel_${relIndex}`}>
                                <Text size={200}>{relationship.from} → {relationship.to}</Text>
                                <div className={styles.relationshipStrengthTrack}>
                                  <div className={styles.relationshipStrengthFill} style={{ width: `${Math.max(10, pct)}%` }} />
                                </div>
                              </div>
                            );
                          })}
                          {relationships.length === 0 && <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No relationship data available yet.</Text>}
                        </div>
                      </Card>
                    );
                  }
                  if (type === "heatmap") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">Topic intensity</Text>} description={<Text size={200}>Relative topic signal strength across dataset.</Text>} />
                        <div className={styles.sectionBody}>
                          {topicShareBars.length > 0 ? topicShareBars.slice(0, 5).map((topic) => (
                            <div key={topic.name} className={styles.barCard}>
                              <Text size={200}>{topic.name}</Text>
                              <div className={styles.barTrack}><div className={styles.barFill} style={{ width: `${Math.max(topic.share, 6)}%`, background: "linear-gradient(90deg, #1d4ed8, #14b8a6)" }} /></div>
                            </div>
                          )) : <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>Topic data not yet available.</Text>}
                        </div>
                      </Card>
                    );
                  }
                  if (type === "metric") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader
                          header={<Text weight="semibold">{block.label || "Key metric"}</Text>}
                          description={<Text className={styles.metricValue}>{block.value != null ? String(block.value) : String(metrics.processed)}</Text>}
                        />
                      </Card>
                    );
                  }
                  if (type === "comparison") {
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">{block.title || "Comparison"}</Text>} />
                        <div className={styles.sectionBody}>
                          <Text size={200}>{block.left_label ?? "Left"}: {block.left_value ?? 0}</Text>
                          <Text size={200}>{block.right_label ?? "Right"}: {block.right_value ?? 0}</Text>
                        </div>
                      </Card>
                    );
                  }
                  if (type === "bullet_list") {
                    const items = Array.isArray(block.items) && block.items.length > 0
                      ? block.items
                      : (data.key_insights || []).slice(0, 4);
                    return (
                      <Card key={blockKey} className={styles.evidenceCard}>
                        <CardHeader header={<Text weight="semibold">Key highlights</Text>} />
                        <div className={styles.sectionBody}>
                          {items.map((item, itemIndex) => (
                            <Text key={`${blockKey}_item_${itemIndex}`} size={200}>· {item}</Text>
                          ))}
                        </div>
                      </Card>
                    );
                  }
                  return (
                    <Card key={blockKey} className={styles.evidenceCard}>
                      <CardHeader header={<Text weight="semibold">{block.title || block.type}</Text>} description={<Text size={200}>AI-generated insight block.</Text>} />
                    </Card>
                  );
                })}
              </div>
            </div>
          </Card>
        )}

        {(metrics.processed !== "—" || metrics.topicsCount > 0 || metrics.entitiesCount > 0 || metrics.kpiCount > 0) && (
        <Card className={styles.sectionCard}>
          <CardHeader
            header={<Text weight="semibold" size={500}>Data overview</Text>}
            description={<Text size={200}>A quick snapshot of record count, extracted topics, entities, and links.</Text>}
          />
          <div className={styles.sectionBody}>
            <div className={styles.overviewGrid}>
              {[
                {
                  icon: <Board24Regular />,
                  label: "Records analyzed",
                  summary: "How many records are in the current view.",
                  value: metrics.processed,
                  color: PALETTE[0],
                },
                {
                  icon: <ChartMultiple24Regular />,
                  label: "Topics identified",
                  summary: "Distinct topics found in document content.",
                  value: metrics.topicsCount,
                  color: PALETTE[1],
                },
                {
                  icon: <Person24Regular />,
                  label: "Entities extracted",
                  summary: "Named entities detected across records.",
                  value: metrics.entitiesCount,
                  color: PALETTE[2],
                },
                {
                  icon: <Link24Regular />,
                  label: "Relationship links",
                  summary: "Detected links between entities/topics.",
                  value: metrics.relationshipsCount,
                  color: PALETTE[3],
                },
              ].map((metric) => (
                <Card key={metric.label} className={styles.metricCard}>
                  <CardHeader
                    image={metric.icon}
                    header={<Text weight="semibold">{metric.label}</Text>}
                    description={
                      <Text className={styles.metricValue} style={{ color: metric.color }}>
                        {typeof metric.value === "number" ? metric.value.toLocaleString() : metric.value}
                      </Text>
                    }
                  />
                  <Text className={styles.metricSubtext}>{metric.summary}</Text>
                </Card>
              ))}
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <Button
                appearance="subtle"
                icon={showMoreOverview ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                onClick={() => setShowMoreOverview((prev) => !prev)}
              >
                {showMoreOverview ? "Hide additional metrics" : "Show additional metrics"}
              </Button>
              <Button appearance="subtle" icon={<ChevronRight20Regular />} onClick={() => nav("/explore")}>Go to Explore</Button>
            </div>

            {showMoreOverview && (
              <Card className={styles.sectionCard}>
                <CardHeader
                  header={<Text weight="semibold" size={400}>Additional metrics</Text>}
                  description={<Text size={200}>Expanded document-grounded metrics for deeper review.</Text>}
                />
                <div className={styles.sectionBody}>
                <div className={styles.overviewGrid}>
                  {moreMetrics.map((metric) => (
                    <Card key={metric.label} className={styles.metricCard}>
                      <CardHeader
                        header={<Text weight="semibold">{metric.label}</Text>}
                        description={
                          <Text className={styles.metricValue} style={{ color: metric.color }}>
                            {metric.value}
                          </Text>
                        }
                      />
                      <Text className={styles.metricSubtext}>{metric.summary}</Text>
                    </Card>
                  ))}
                </div>
                </div>
              </Card>
            )}
          </div>
        </Card>
        )}

        {hasSparseSignal && (
          <Card className={styles.noticeCard}>
            <CardHeader
              image={<Info24Regular />}
              header={<Text weight="semibold" size={400}>Low insight signal detected</Text>}
              description={<Text size={200}>The current filter selection returned limited topic/entity detail. Try refreshing or broadening filters.</Text>}
              action={
                <Button appearance="subtle" icon={<ArrowSync24Regular />} onClick={() => load(filters, true)}>
                  Refresh now
                </Button>
              }
            />
            <div className={styles.sectionBody}>
              <Button appearance="secondary" icon={<ChevronRight20Regular />} onClick={() => nav("/explore")}>Review records in Explore</Button>
            </div>
          </Card>
        )}

        {runtime?.actions?.length ? (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Suggested explorations</Text>}
              description={<Text size={200}>Conversation-ready prompts to drill into AI findings.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.discoveryGrid}>
                {runtime.actions.slice(0, 6).map((action: any, index: number) => (
                  <Button
                    key={action.id || index}
                    className={styles.discoveryButton}
                    appearance="secondary"
                    onClick={() => nav(`/explore?q=${encodeURIComponent(toConversationalPrompt(action.label))}&source=insights`)}
                  >
                    {toConversationalPrompt(action.label)}
                  </Button>
                ))}
              </div>
            </div>
          </Card>
        ) : null}

        {rankedInsights.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>AI findings</Text>}
              description={<Text size={200}>Ranked by impact score, confidence, and evidence.</Text>}
              action={
                <Tooltip content="Cards are generated from the strongest findings available for the current dataset." relationship="description">
                  <Button appearance="subtle" icon={<Info24Regular />} aria-label="Document findings help" />
                </Tooltip>
              }
            />
            <div className={styles.sectionBody}>
              <div className={styles.insightGrid}>
                {rankedInsights.map((insight: any, index: number) => {
                  const findingId = String(insight.id || `finding_${index + 1}`);
                  const isExpanded = expandedFindings.has(findingId);
                  const severity = insight.severity || "Insight";
                  const severityStyle = getSeverityStyle(severity);
                  const confidence = typeof insight.confidence === "number" ? Math.round(insight.confidence * 100) : null;
                  const explainability =
                    insight.explanation ||
                    insight.context ||
                    chartEvidence[0] ||
                    "This finding is inferred from recurring patterns in the filtered records.";

                  return (
                    <Card
                      key={findingId}
                      className={styles.insightCard}
                      style={{ borderLeft: `3px solid ${severityStyle.accent}`, border: `1px solid #e5e7eb`, background: "#fff" }}
                    >
                      <CardHeader
                        image={<Alert24Regular style={{ color: severityStyle.accent }} />}
                        header={
                          <div className={styles.findingsHeaderRow}>
                            <div className={styles.severityRow}>
                              <Badge appearance="tint" color={severityStyle.badge} size="small">
                                {severity}
                              </Badge>
                              <span className={styles.scorePill}>Score {insight.score ?? 0}</span>
                              {confidence !== null && <Badge appearance="outline" size="small">{confidence}% confidence</Badge>}
                            </div>
                            <Button
                              appearance="subtle"
                              size="small"
                              icon={isExpanded ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                              onClick={() => toggleFinding(findingId)}
                            >
                              {isExpanded ? "Collapse" : "Explain"}
                            </Button>
                          </div>
                        }
                        description={<Text weight="semibold" style={{ color: "#0f172a" }}>{insight.title}</Text>}
                      />
                      <div className={styles.insightBody}>
                        {insight.context && insight.context !== insight.title && (
                          <Text size={200} style={{ color: "#475569" }}>{insight.context}</Text>
                        )}
                        {Array.isArray(insight.aiTags) && insight.aiTags.length > 0 && (
                          <div className={styles.tagRow}>
                            {insight.aiTags.slice(0, 4).map((tag: string) => (
                              <Badge key={`${findingId}_${tag}`} size="small" appearance="outline">#{tag}</Badge>
                            ))}
                          </div>
                        )}
                        {isExpanded && (
                          <>
                            <div className={styles.explainBox}>
                              <Text size={200} weight="semibold">Why this matters</Text>
                              <Text size={200} style={{ display: "block", color: "#64748b" }}>{explainability}</Text>
                            </div>
                            <div className={styles.explainBox}>
                              <Text size={200} weight="semibold">Visual evidence</Text>
                              {(chartEvidence.length > 0 ? chartEvidence : ["No structured chart evidence available yet."]).slice(0, 2).map((evidence, evIndex) => (
                                <Text key={`${findingId}_ev_${evIndex}`} size={200} style={{ display: "block", color: "#64748b" }}>- {evidence}</Text>
                              ))}
                            </div>
                          </>
                        )}
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          </Card>
        )}

        {aiTimeline.length > 0 ? (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Unexpected patterns</Text>}
              description={<Text size={200}>Timeline view of notable deviations and AI-detected shifts.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.timelineList}>
                {aiTimeline.slice(0, 6).map((item, index) => (
                  <div key={item.id || index} className={styles.timelineItem}>
                    <div className={styles.timelineDot} />
                    <Card className={styles.evidenceCard}>
                      <CardHeader
                        image={<Alert24Regular />}
                        header={<Text weight="semibold">{item.marker}</Text>}
                        description={<Text size={200}>{item.title}</Text>}
                      />
                      <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: "block", padding: "0 16px 16px" }}>
                        {item.description}
                      </Text>
                    </Card>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        ) : null}

        {(topicBars.length > 0 || entityBars.length > 0) && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Knowledge distribution</Text>}
              description={<Text size={200}>See which topics dominate and which entities are mentioned most.</Text>}
              action={
                <Tooltip content="Left card uses percentage share of topic score. Right card uses raw entity mention totals." relationship="description">
                  <Button appearance="subtle" icon={<Info24Regular />} aria-label="Knowledge distribution help" />
                </Tooltip>
              }
            />
            <div className={styles.sectionBody}>
              <div className={styles.distributionStack}>
                {topicShareBars.length > 0 && (
                  <Card className={styles.sectionCard}>
                    <CardHeader
                      header={<Text weight="semibold" size={400}>Topic share</Text>}
                      description={<Text size={200}>Relative share of each detected topic across the total topic signal.</Text>}
                      action={<Badge appearance="tint" color="brand" size="small">{topicShareBars.length}</Badge>}
                    />
                    <div className={styles.sectionBody}>
                      <div className={styles.topicList}>
                        {topicShareBars.map((topic) => {
                          const width = `${Math.max(topic.share, 4)}%`;
                          const displayValue = `${topic.share.toFixed(1)}%`;
                          return (
                            <div key={topic.name} className={styles.barCard}>
                              <div className={styles.barLabel}>
                                <Text className={styles.topicName} title={topic.name}>{topic.name}</Text>
                                <Badge appearance="outline" size="small">{displayValue}</Badge>
                              </div>
                              <div className={styles.barTrack}>
                                <div className={styles.barFill} style={{ width, background: `linear-gradient(90deg, ${topic.fill}, ${topic.fill}CC)` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </Card>
                )}

                {entityBars.length > 0 && (
                  <Card className={styles.sectionCard}>
                    <CardHeader
                      header={<Text weight="semibold" size={400}>Entity frequency</Text>}
                      description={<Text size={200}>Absolute mention counts for the most frequent extracted entities.</Text>}
                      action={<Badge appearance="tint" color="brand" size="small">{entityBars.length}</Badge>}
                    />
                    <div className={styles.sectionBody}>
                      <ResponsiveContainer width="100%" height={320}>
                        <RBarChart data={entityBars.slice(0, 10)} layout="vertical" margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis dataKey="name" type="category" width={160} />
                          <ReTooltip formatter={(value: number) => [Number(value).toLocaleString(), "Mentions"]} />
                          <Bar dataKey="mentions" radius={[0, 8, 8, 0]} fill="#14b8a6" />
                        </RBarChart>
                      </ResponsiveContainer>
                    </div>
                  </Card>
                )}
              </div>
            </div>
          </Card>
        )}

        {relationships.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Top connections</Text>}
              description={<Text size={200}>Most meaningful links with AI-estimated connection strength.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.distributionGrid}>
                {relationships.map((relationship, index) => (
                  <Card key={index} className={styles.evidenceCard}>
                    <CardHeader
                      header={<Text weight="semibold">{relationship.from}</Text>}
                      description={<Text size={200}>{relationship.relation || "related"}</Text>}
                    />
                    <Text size={200} style={{ display: "block", padding: "0 16px 12px" }}>{relationship.to}</Text>
                    <div style={{ padding: "0 16px 16px" }}>
                      <div className={styles.relationshipStrengthRow}>
                        <Badge appearance="outline" size="small">
                          {hasConnectionStrengthVariance
                            ? `Strength ${(relationship.strength || 0).toFixed(2)}`
                            : "Observed pattern"}
                        </Badge>
                        <div className={styles.relationshipStrengthTrack}>
                          <div
                            className={styles.relationshipStrengthFill}
                            style={{ width: `${Math.max(10, (Number(relationship.strength || 0) / maxRelationshipStrength) * 100)}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </Card>
        )}

        {rankedKpis.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>KPI snapshot</Text>}
              description={<Text size={200}>Top-ranked KPI values with trend and confidence context.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.overviewGrid}>
                {rankedKpis.map((kpi, index) => (
                  <Card key={index} className={styles.metricCard} style={{ borderTop: `3px solid ${PALETTE[index % PALETTE.length]}` }}>
                    <CardHeader
                      header={<Text weight="semibold">{kpi.label}</Text>}
                      description={
                        <div>
                          <Text className={styles.metricValue} style={{ color: PALETTE[index % PALETTE.length] }}>{fmtKpi(kpi)}</Text>
                          <div className={styles.severityRow} style={{ marginTop: 8 }}>
                            <Badge size="small" appearance="outline">Trend: {kpi.trendDirection || "stable"}</Badge>
                            {typeof kpi.confidence === "number" && (
                              <Badge size="small" appearance="outline">{Math.round(kpi.confidence * 100)}% confidence</Badge>
                            )}
                          </div>
                        </div>
                      }
                    />
                  </Card>
                ))}
              </div>
            </div>
          </Card>
        )}

        {rankedInsights.length > 0 && (
          <Card className={styles.tipCard}>
            <CardHeader
              header={<Text weight="semibold" size={400}>Tip</Text>}
              description={<Text size={200}>Use the Explore page to dig into a finding and validate anomalies with follow-up questions.</Text>}
            />
          </Card>
        )}
      </div>
    </div>
  );
};

export default Insights;
