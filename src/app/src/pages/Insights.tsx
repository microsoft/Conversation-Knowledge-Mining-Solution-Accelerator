import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Divider,
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
  Dismiss24Regular,
  DocumentBulletList20Regular,
  Info24Regular,
  Link24Regular,
  Person24Regular,
  Sparkle24Regular,
} from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";
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
import type { DashboardResponse, KPI } from "../types/api";

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
  progressTrack: {
    width: "100%",
    maxWidth: "180px",
    height: "6px",
    borderRadius: "999px",
    backgroundColor: tokens.colorNeutralStroke2,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: "999px",
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
  entityTopGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: "12px",
  },
  entityCard: {
    borderRadius: "16px",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.05)",
  },
  entityBarList: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
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
  emptyState: {
    padding: "20px",
    color: tokens.colorNeutralForeground3,
  },
  panelOverlay: {
    position: "fixed",
    inset: 0,
    backgroundColor: "rgba(15, 23, 42, 0.42)",
    zIndex: 50,
  },
  panelCard: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    width: "min(100vw, 440px)",
    borderRadius: 0,
    boxShadow: "-20px 0 50px rgba(15, 23, 42, 0.15)",
    display: "flex",
    flexDirection: "column",
  },
  panelBody: {
    padding: "0 18px 18px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    overflowY: "auto",
    flex: 1,
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
});

interface EvidenceItem {
  text: string;
  label?: string;
  value?: number | string;
  section?: string;
}

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

const deriveRuntimeFromDashboard = (dashboard: DashboardResponse) => {
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

  const classify = (text: string) => {
    const lower = text.toLowerCase();
    if (lower.includes("risk") || lower.includes("concern")) return "Risk" as const;
    if (lower.includes("anomaly") || lower.includes("unusual") || lower.includes("spike") || lower.includes("drop")) return "Critical" as const;
    if (lower.includes("opportun") || lower.includes("potential")) return "High" as const;
    if (lower.includes("trend") || lower.includes("increase") || lower.includes("decrease")) return "High" as const;
    return "Medium" as const;
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
      trendDirection: kpi.trend === "up" ? "up" : kpi.trend === "down" ? "down" : "stable",
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

const EvidencePanel: React.FC<{
  visible: boolean;
  insightTitle?: string;
  evidence?: EvidenceItem[];
  onClose: () => void;
}> = ({ visible, insightTitle, evidence, onClose }) => {
  const styles = useStyles();

  if (!visible) return null;

  return (
    <div className={styles.panelOverlay} role="dialog" aria-modal="true" aria-label="Supporting evidence">
      <Card className={styles.panelCard}>
        <CardHeader
          header={<Text weight="semibold" size={500}>Supporting evidence</Text>}
          description={insightTitle ? <Text size={200}>For: {insightTitle}</Text> : undefined}
          action={<Button appearance="subtle" icon={<Dismiss24Regular />} onClick={onClose} />}
        />
        <Divider />
        <div className={styles.panelBody}>
          {!evidence?.length ? (
            <Card className={styles.evidenceCard}>
              <Text size={200}>No supporting evidence found for this insight.</Text>
            </Card>
          ) : (
            evidence.map((item, index) => (
              <Card key={index} className={styles.evidenceCard}>
                <CardHeader
                  header={<Text weight="semibold">{item.label || "Evidence item"}</Text>}
                  description={item.section ? <Text size={200}>{item.section}</Text> : undefined}
                />
                <Text size={200}>{item.text}</Text>
                {item.value !== undefined && <Text size={200}>Count: {item.value}</Text>}
              </Card>
            ))
          )}
        </div>
      </Card>
    </div>
  );
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
  if (severity === "Critical") return { badge: "danger" as const, accent: "#dc2626", text: "#991b1b" };
  if (severity === "High") return { badge: "warning" as const, accent: "#ea580c", text: "#9a3412" };
  if (severity === "Risk") return { badge: "danger" as const, accent: "#dc2626", text: "#991b1b" };
  if (severity === "Opportunity") return { badge: "success" as const, accent: "#16a34a", text: "#166534" };
  if (severity === "Trend") return { badge: "brand" as const, accent: "#2563eb", text: "#1d4ed8" };
  return { badge: "brand" as const, accent: "#2563eb", text: "#1d4ed8" };
};

const Insights: React.FC = () => {
  const styles = useStyles();
  const nav = useNavigate();
  const { setDashboardHeadline, insights: cachedData, setInsights } = useAppState();

  const [data, setData] = useState<DashboardResponse | null>(cachedData);
  const [loading, setLoading] = useState(!cachedData);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters] = useState<Record<string, string>>({});
  const [evidencePanelOpen, setEvidencePanelOpen] = useState(false);
  const [selectedEvidenceData, setSelectedEvidenceData] = useState<EvidenceItem[]>([]);
  const [selectedInsight, setSelectedInsight] = useState<string | null>(null);
  const [showMoreOverview, setShowMoreOverview] = useState(false);

  const load = useCallback(async (filterValues?: Record<string, string>, refresh = false) => {
    if (refresh) setLoading(true);
    else setRefreshing(true);
    setError(null);

    try {
      const response = await getDashboard(filterValues, refresh);
      setData(response.data);
      setInsights(response.data);
      if (response.data?.headline) setDashboardHeadline(response.data.headline);
    } catch {
      setError("Failed to load dashboard. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [setDashboardHeadline, setInsights]);

  useEffect(() => {
    if (!cachedData || !cachedData.runtime) {
      load();
    }
  }, [cachedData, load]);

  const runtime = useMemo(() => data?.runtime ?? (data ? deriveRuntimeFromDashboard(data) : null), [data]);
  const dataset = data?.datasetInfo || { name: "Dataset", sourceType: "documents", lastUpdated: new Date().toISOString() };

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
      if (lower.includes("risk") || lower.includes("anomaly")) return "Risk";
      if (lower.includes("opportun")) return "Opportunity";
      if (lower.includes("trend")) return "Trend";
      return "Insight";
    };

    const order: Record<string, number> = { Risk: 0, Opportunity: 1, Trend: 2, Insight: 3 };

    return source
      .map((insight) => ({
        ...insight,
        severity: toSeverity(insight.category),
      }))
      .sort((a, b) => (order[a.severity] ?? 99) - (order[b.severity] ?? 99))
      .slice(0, 4);
  }, [runtime, data]);

  const topicBars = useMemo(() => (runtime?.topics || [])
    .filter((topic) => !isTestLabel(topic.name))
    .sort((a, b) => (b.score || 0) - (a.score || 0))
    .slice(0, 20)
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
      .slice(0, 10)
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

  const moreMetrics = [
    { label: "Key insights", value: metrics.insightsCount, summary: "How many key insights were returned for this dataset.", tooltip: "Count of `key_insights` in the current dashboard response.", color: PALETTE[4] },
    { label: "Standout findings", value: metrics.findingsCount, summary: "How many standout findings were highlighted.", tooltip: "Count of `standout_findings` in the current response.", color: PALETTE[5] },
    { label: "Analysis sections", value: metrics.sectionsCount, summary: "How many analysis blocks were generated.", tooltip: "Count of `sections` generated from your records.", color: PALETTE[6] },
    { label: "Suggested questions", value: metrics.questionsCount, summary: "Suggested follow-up questions you can ask next.", tooltip: "Count of `suggested_questions` provided by the service.", color: PALETTE[7] },
    { label: "KPI metrics", value: metrics.kpiCount, summary: "Number of KPI values currently shown.", tooltip: "Count of KPI entries in `runtime.kpis`.", color: PALETTE[0] },
    { label: "Flagged patterns", value: metrics.anomaliesCount, summary: "Potential outliers or unusual patterns detected.", tooltip: "Count of `runtime.unexpectedPatterns` in this run.", color: PALETTE[3] },
  ];

  const summarySignals = Array.from(new Set([
    data?.headline,
    ...(runtime?.summarySignals || []),
  ].filter((value): value is string => Boolean(value)))).slice(0, 6);

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

            {summarySignals.length > 0 && (
              <div className={styles.signalRow}>
                {summarySignals.map((signal, index) => (
                  <Badge key={`${signal}-${index}`} appearance="outline" color="brand">
                    {signal}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card className={styles.sectionCard}>
          <CardHeader
            header={<Text weight="semibold" size={500}>Data overview</Text>}
            description={<Text size={200}>A quick snapshot of record count, extracted topics, entities, and links.</Text>}
            action={
              <Tooltip content="These top numbers come from `data_context` and runtime extraction counts in this response." relationship="description">
                <Button appearance="subtle" icon={<Info24Regular />} aria-label="Data overview help" />
              </Tooltip>
            }
          />
          <div className={styles.sectionBody}>
            <div className={styles.overviewGrid}>
              {[
                {
                  icon: <Board24Regular />,
                  label: "Records analyzed",
                  summary: "How many records are in the current view.",
                  tooltip: "Uses `filtered_records` when filters are applied, otherwise `total_records`.",
                  value: metrics.processed,
                  color: PALETTE[0],
                },
                {
                  icon: <ChartMultiple24Regular />,
                  label: "Topics identified",
                  summary: "Distinct topics found in document content.",
                  tooltip: "Count of topic entries extracted into `runtime.topics`.",
                  value: metrics.topicsCount,
                  color: PALETTE[1],
                },
                {
                  icon: <Person24Regular />,
                  label: "Entities extracted",
                  summary: "Named entities detected across records.",
                  tooltip: "Count of entity entries in `runtime.entities`.",
                  value: metrics.entitiesCount,
                  color: PALETTE[2],
                },
                {
                  icon: <Link24Regular />,
                  label: "Relationship links",
                  summary: "Detected links between entities/topics.",
                  tooltip: "Count of relationship entries in `runtime.relationships`.",
                  value: metrics.relationshipsCount,
                  color: PALETTE[3],
                },
              ].map((metric) => (
                <Card key={metric.label} className={styles.metricCard}>
                  <CardHeader
                    image={metric.icon}
                    header={
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Text weight="semibold">{metric.label}</Text>
                        <Tooltip content={metric.tooltip} relationship="description">
                          <Info24Regular fontSize={14} />
                        </Tooltip>
                      </div>
                    }
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
              <Button appearance="subtle" icon={<ChevronRight20Regular />} onClick={() => nav("/explore")}>Open explorer</Button>
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
                        header={
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <Text weight="semibold">{metric.label}</Text>
                            <Tooltip content={metric.tooltip} relationship="description">
                              <Info24Regular fontSize={14} />
                            </Tooltip>
                          </div>
                        }
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

        {runtime?.actions?.length ? (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Suggested explorations</Text>}
              description={<Text size={200}>Quick prompts to continue the analysis.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.discoveryGrid}>
                {runtime.actions.slice(0, 6).map((action: any, index: number) => (
                  <Button
                    key={action.id || index}
                    className={styles.discoveryButton}
                    appearance="secondary"
                    onClick={() => nav(`/explore?q=${encodeURIComponent(action.label)}&source=insights`)}
                  >
                    {action.label}
                  </Button>
                ))}
              </div>
            </div>
          </Card>
        ) : null}

        {rankedInsights.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Document findings</Text>}
              description={<Text size={200}>The most important findings detected from your current document set.</Text>}
              action={
                <Tooltip content="Cards are built from `runtime.insights`; if missing, we fall back to `key_insights` and `standout_findings`." relationship="description">
                  <Button appearance="subtle" icon={<Info24Regular />} aria-label="Document findings help" />
                </Tooltip>
              }
            />
            <div className={styles.sectionBody}>
              <div className={styles.insightGrid}>
                {rankedInsights.map((insight: any, index: number) => {
                  const severity = insight.severity || "Medium";
                  const severityStyle = getSeverityStyle(severity);
                  const confidence = typeof insight.confidence === "number" ? Math.round(insight.confidence * 100) : null;

                  return (
                    <Card
                      key={insight.id || index}
                      className={styles.insightCard}
                      style={{ borderLeft: `4px solid ${severityStyle.accent}` }}
                    >
                      <CardHeader
                        image={<Alert24Regular />}
                        header={
                          <div className={styles.severityRow}>
                            <Badge appearance="tint" color={severityStyle.badge} size="small">
                              {severity}
                            </Badge>
                            {confidence !== null && <Badge appearance="outline" size="small">{confidence}% confidence</Badge>}
                          </div>
                        }
                        description={<Text weight="semibold" style={{ color: severityStyle.text }}>{insight.title}</Text>}
                      />
                      <div className={styles.insightBody}>
                        {insight.context && insight.context !== insight.title && (
                          <Text size={200} style={{ color: severityStyle.text }}>{insight.context}</Text>
                        )}
                        {insight.explanation && insight.explanation !== insight.title && (
                          <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>{insight.explanation}</Text>
                        )}
                        <Button
                          size="small"
                          appearance="secondary"
                          icon={<DocumentBulletList20Regular />}
                          onClick={() => {
                            setSelectedInsight(insight.title);
                            setSelectedEvidenceData(insight.evidence || []);
                            setEvidencePanelOpen(true);
                          }}
                        >
                          View evidence
                        </Button>
                      </div>
                    </Card>
                  );
                })}
              </div>
            </div>
          </Card>
        )}

        {runtime?.unexpectedPatterns?.length ? (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Unexpected patterns</Text>}
              description={<Text size={200}>Notable deviations that deserve a closer look.</Text>}
            />
            <div className={styles.sectionBody}>
              <div className={styles.distributionGrid}>
                {(runtime.unexpectedPatterns || []).slice(0, 4).map((pattern: any, index: number) => {
                  const high = pattern.severity === "high";
                  return (
                    <Card
                      key={pattern.id || index}
                      className={styles.evidenceCard}
                      style={{ background: high ? "#fff1f2" : "#fffbeb", border: `1px solid ${high ? "#fecdd3" : "#fde68a"}` }}
                    >
                      <CardHeader
                        image={<Alert24Regular />}
                        header={<Text weight="semibold">{high ? "Critical deviation" : "Unusual pattern"}</Text>}
                        description={<Text size={200}>{pattern.pattern}</Text>}
                      />
                      <Text size={200} style={{ color: tokens.colorNeutralForeground3, display: "block", padding: "0 16px 16px" }}>
                        {pattern.explanation}
                      </Text>
                    </Card>
                  );
                })}
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
                <Card className={styles.sectionCard}>
                  <CardHeader
                    header={<Text weight="semibold" size={400}>Topic share</Text>}
                    description={<Text size={200}>Relative share of each detected topic across the total topic signal.</Text>}
                    action={<Badge appearance="tint" color="brand" size="small">{topicShareBars.length}</Badge>}
                  />
                  <div className={styles.sectionBody}>
                    {topicShareBars.length > 0 ? (
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
                    ) : (
                      <Text size={200} style={{ color: tokens.colorNeutralForeground3 }}>No topics to display.</Text>
                    )}
                  </div>
                </Card>

                <Card className={styles.sectionCard}>
                  <CardHeader
                    header={<Text weight="semibold" size={400}>Entity frequency</Text>}
                    description={<Text size={200}>Absolute mention counts for the most frequent extracted entities.</Text>}
                    action={<Badge appearance="tint" color="brand" size="small">{entityBars.length}</Badge>}
                  />
                  <div className={styles.sectionBody}>
                    {entityBars.length > 0 && (
                      <ResponsiveContainer width="100%" height={320}>
                        <RBarChart data={entityBars.slice(0, 10)} layout="vertical" margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis type="number" />
                          <YAxis dataKey="name" type="category" width={160} />
                          <ReTooltip formatter={(value: number) => [Number(value).toLocaleString(), "Mentions"]} />
                          <Bar dataKey="mentions" radius={[0, 8, 8, 0]} fill="#14b8a6" />
                        </RBarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </Card>
              </div>
            </div>
          </Card>
        )}

        {relationships.length > 0 && (
          <Card className={styles.sectionCard}>
            <CardHeader
              header={<Text weight="semibold" size={500}>Top connections</Text>}
              description={<Text size={200}>Most meaningful links found between high-signal categories and values.</Text>}
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
                      <Badge appearance="outline" size="small">
                        {hasConnectionStrengthVariance
                          ? `Strength ${(relationship.strength || 0).toFixed(2)}`
                          : "Observed pattern"}
                      </Badge>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </Card>
        )}

        <Card className={styles.sectionCard}>
          <CardHeader
            header={<Text weight="semibold" size={500}>KPI snapshot</Text>}
            description={<Text size={200}>Top KPI values calculated from the current records and filters.</Text>}
          />
          <div className={styles.sectionBody}>
            <div className={styles.overviewGrid}>
              {(runtime?.kpis || []).slice(0, 8).map((kpi, index) => (
                <Card key={index} className={styles.metricCard} style={{ borderTop: `3px solid ${PALETTE[index % PALETTE.length]}` }}>
                  <CardHeader
                    header={<Text weight="semibold">{kpi.label}</Text>}
                    description={<Text className={styles.metricValue} style={{ color: PALETTE[index % PALETTE.length] }}>{fmtKpi(kpi)}</Text>}
                  />
                </Card>
              ))}
            </div>
          </div>
        </Card>

        <Card className={styles.tipCard}>
          <CardHeader
            header={<Text weight="semibold" size={400}>Tip</Text>}
            description={<Text size={200}>Use the chat panel to dig into a finding, validate an anomaly, or ask for source evidence.</Text>}
          />
        </Card>
      </div>

      <EvidencePanel
        visible={evidencePanelOpen}
        insightTitle={selectedInsight || undefined}
        evidence={selectedEvidenceData}
        onClose={() => setEvidencePanelOpen(false)}
      />
    </div>
  );
};

export default Insights;
