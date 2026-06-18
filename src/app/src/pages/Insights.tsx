import React, { useState, useEffect } from "react";
import { Button, Spinner, Dropdown, Option, Skeleton, SkeletonItem } from "@fluentui/react-components";
import { ArrowSync24Regular, ChartMultiple24Regular, ErrorCircle24Regular } from "@fluentui/react-icons";
import { DonutChart, BarChart, LineChart } from "../components/Charts";
import { useNavigate } from "react-router-dom";
import { getDashboard } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import type { DashboardResponse, KPI, ChartSpec } from "../types/api";
import s from "./Insights.module.css";

const WORD_COLORS = ["#2563eb", "#7c3aed", "#059669", "#dc2626", "#f59e0b", "#ec4899", "#0ea5e9", "#f97316"];

const Insights: React.FC = () => {
  const nav = useNavigate();
  const { setDashboardHeadline, insights: cachedData, setInsights } = useAppState();
  const [data, setData] = useState<DashboardResponse | null>(cachedData);
  const [loading, setLoading] = useState(!cachedData);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = async (f?: Record<string, string>, refresh = false) => {
    if (data && !refresh) {
      setRefreshing(true); // filter change — keep existing data visible
    } else {
      setLoading(true); // initial load or re-generate — show skeleton
    }
    setError(null);
    try {
      const r = await getDashboard(f, refresh);
      setData(r.data);
      setInsights(r.data);
      if (r.data?.headline) {
        setDashboardHeadline(r.data.headline);
        try { sessionStorage.setItem("km_headline", JSON.stringify(r.data.headline)); } catch {}
      }
    } catch (e) {
      setError("Failed to load dashboard. Please try again.");
    }
    finally { setLoading(false); setRefreshing(false); }
  };

  // Use cached insights on page re-entry; refresh explicitly via Re-generate.
  // Upload/delete flows invalidate cache (setInsights(null)), which triggers a fresh load.
  useEffect(() => { if (!cachedData) load(); }, []);

  const applyFilter = (field: string, value: string) => {
    const next = { ...filters };
    if (!value || value === "_all") delete next[field];
    else next[field] = value;
    setFilters(next);
    load(next);
  };

  const fmt = (kpi: KPI) => {
    if (kpi.format === "percentage") return `${kpi.value}%`;
    if (kpi.format === "minutes") return `${kpi.value}mins`;
    return kpi.value?.toLocaleString?.() ?? kpi.value;
  };

  const SkeletonDashboard = () => (
    <div className={s.content}>
      <Skeleton aria-label="Loading insights">
        <div className={s.datasetHeader}>
          <div style={{ flex: 1 }}>
            <SkeletonItem shape="rectangle" size={20} style={{ width: 220 }} />
          </div>
          <SkeletonItem shape="rectangle" size={32} style={{ width: 110, borderRadius: 6 }} />
        </div>
      </Skeleton>

      <Skeleton>
        <div className={s.insightsRow}>
          <div className={s.insightsCard}>
            <SkeletonItem shape="rectangle" size={16} style={{ width: 120, marginBottom: 12 }} />
            <SkeletonItem shape="rectangle" size={12} style={{ width: "90%", marginBottom: 8 }} />
            <SkeletonItem shape="rectangle" size={12} style={{ width: "75%", marginBottom: 8 }} />
            <SkeletonItem shape="rectangle" size={12} style={{ width: "60%" }} />
          </div>
          <div className={s.insightsCard}>
            <SkeletonItem shape="rectangle" size={16} style={{ width: 140, marginBottom: 12 }} />
            <SkeletonItem shape="rectangle" size={12} style={{ width: "85%", marginBottom: 8 }} />
            <SkeletonItem shape="rectangle" size={12} style={{ width: "70%" }} />
          </div>
        </div>
      </Skeleton>

      <Skeleton>
        <div className={s.kpiRow}>
          {[1, 2, 3, 4].map(i => (
            <div key={i} className={s.kpi}>
              <SkeletonItem shape="rectangle" size={12} style={{ width: 80, marginBottom: 8 }} />
              <SkeletonItem shape="rectangle" size={28} style={{ width: 60 }} />
            </div>
          ))}
        </div>
      </Skeleton>

      <Skeleton>
        <div className={s.dashboardGrid}>
          {[1, 2, 3, 4].map(i => (
            <div key={i} className={s.gridItem}>
              <div className={s.chartCard}>
                <SkeletonItem shape="rectangle" size={16} style={{ width: 160, marginBottom: 16 }} />
                <SkeletonItem shape="rectangle" size={16} style={{ width: "100%", height: 180, borderRadius: 8 }} />
              </div>
            </div>
          ))}
        </div>
      </Skeleton>
    </div>
  );

  if (loading) return (
    <div className={s.page}><SkeletonDashboard /></div>
  );

  if (error && !data) return (
    <div className={s.page}><div className={s.empty}>
      <ErrorCircle24Regular style={{ fontSize: 48, color: "#dc2626" }} />
      <h2>Something went wrong</h2><p>{error}</p>
      <Button appearance="primary" onClick={() => load()}>Try again</Button>
    </div></div>
  );

  if (!data || (data.data_context?.total_records ?? 0) === 0) return (
    <div className={s.page}><div className={s.empty}>
      <ChartMultiple24Regular style={{ fontSize: 48 }} />
      <h2>No Data Available</h2><p>Upload documents to see insights.</p>
      <Button appearance="primary" onClick={() => nav("/")}>Upload data</Button>
    </div></div>
  );

  const sections = data.sections || [];
  const kpis = data.kpis || [];
  const availableFilters = data.filters || [];
  const filterLabelMap = Object.fromEntries(
    availableFilters.map((f: any) => [f.field, f.label || f.field])
  ) as Record<string, string>;
  const questions = data.suggested_questions || [];
  const keyInsights = data.key_insights || [];
  const standoutFindings = data.standout_findings || [];

  // Flatten all charts into a single list, with donut + word_cloud adjacent
  const gridCharts: ChartSpec[] = (() => {
    const all: ChartSpec[] = sections.flatMap((sec) =>
      (sec.charts || []).map((chart) => ({ ...chart, sectionId: sec.id }))
    );
    const donutIdx = all.findIndex((c) => c.visualization === "donut");
    const wcIdx = all.findIndex((c) => c.visualization === "word_cloud");
    if (donutIdx >= 0 && wcIdx >= 0 && Math.abs(donutIdx - wcIdx) > 1) {
      const sorted = [...all];
      const wc = sorted.splice(sorted.findIndex((c) => c.visualization === "word_cloud"), 1)[0];
      const di = sorted.findIndex((c) => c.visualization === "donut");
      sorted.splice(di + 1, 0, wc);
      return sorted;
    }
    return all;
  })();

  return (
    <div className={s.page}>
      <div className={s.content} style={refreshing ? { opacity: 0.5, pointerEvents: "none", transition: "opacity 0.2s" } : undefined}>
        {/* ── Dataset header ── */}
        <div className={s.datasetHeader}>
          <div style={{ flex: 1 }}>
            <div className={s.datasetTitle}>{data.headline || "Data Insights"}</div>
          </div>
          <Button appearance="subtle" size="small" icon={<ArrowSync24Regular />}
            onClick={() => load(filters, true)} disabled={loading || refreshing}>
            {loading ? "Analyzing..." : refreshing ? "Updating..." : "Re-generate"}
          </Button>
        </div>

        {/* ── Key Insights + What Stands Out side by side ── */}
        {(keyInsights.length > 0 || standoutFindings.length > 0) && (
          <div className={s.insightsRow}>
            {keyInsights.length > 0 && (
              <div className={s.insightsCard}>
                <div className={s.insightsTitle}>Key Insights</div>
                <ul className={s.insightsList}>
                  {keyInsights.map((insight: string, i: number) => (
                    <li key={i}>{insight}</li>
                  ))}
                </ul>
              </div>
            )}
            {standoutFindings.length > 0 && (
              <div className={s.insightsCard}>
                <div className={s.insightsTitle}>What Stands Out</div>
                <ul className={s.insightsList}>
                  {standoutFindings.map((finding: string, i: number) => (
                    <li key={i}>{finding}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* ── Filters ── */}
        {availableFilters.length > 0 && (
          <>
            <div className={s.filterRow}>
              {availableFilters.map((f: any) => (
                <Dropdown key={f.field} placeholder={f.label}
                  value={filters[f.field] ? `${f.label}: ${filters[f.field]}` : `All ${f.label}`}
                  onOptionSelect={(_, opt) => applyFilter(f.field, opt?.optionValue || "")}
                  size="small" style={{ minWidth: 190 }}>
                  <Option value="_all" text={`All ${f.label}`}>All {f.label}</Option>
                  {f.values.map((v: string) => (
                    <Option key={v} value={v} text={`${f.label}: ${v}`}>{v}</Option>
                  ))}
                </Dropdown>
              ))}
              {Object.keys(filters).length > 0 && (
                <Button size="small" appearance="subtle" onClick={() => { setFilters({}); load({}); }}>
                  Clear {Object.keys(filters).length > 1 ? `(${Object.keys(filters).length})` : ""}
                </Button>
              )}
            </div>

            {Object.keys(filters).length > 0 && (
              <div className={s.filterRow} style={{ marginTop: 8, gap: 6 }}>
                {Object.entries(filters).map(([field, value]) => (
                  <span
                    key={field}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      padding: "4px 8px",
                      borderRadius: 999,
                      background: "#eff6ff",
                      color: "#1e40af",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    {(filterLabelMap[field] || field)}: {value}
                  </span>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── KPIs ── */}
        {kpis.length > 0 && (
          <div className={s.kpiRow}>
            {kpis.map((kpi: any, i: number) => (
              <div key={i} className={s.kpi}>
                <div className={s.kpiLabel}>{kpi.label}</div>
                <div className={s.kpiValue}>{fmt(kpi)}</div>
              </div>
            ))}
          </div>
        )}

        {/* ── All charts in 2-column grid ── */}
        {gridCharts.length > 0 && (
          <div className={s.dashboardGrid}>
            {gridCharts.filter(isValidChart).map((chart: any, i: number) => {
              const isWide = chart.visualization === "driver_table" ||
                             chart.visualization === "table";
              return (
                <div key={i} className={isWide ? s.gridItemFull : s.gridItem}>
                  <ChartCard chart={chart} />
                </div>
              );
            })}
          </div>
        )}

        {/* ── Explore Further ── */}
        {questions.length > 0 && (
          <div className={s.card}>
            <div className={s.cardTitle}>Explore Further</div>
            <div className={s.questionRow}>
              {questions.map((q: string, i: number) => (
                <button key={i} className={s.questionBtn}
                  onClick={() => nav(`/explore?q=${encodeURIComponent(q)}`)}>{q}</button>
              ))}
            </div>
          </div>
        )}

        <div className={s.disclaimer}>AI-generated content may be incorrect</div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════
   Chart validation — skip broken/empty charts
   ═══════════════════════════════════════════ */
const isValidChart = (chart: any): boolean => {
  if (!chart?.visualization || !chart?.title) return false;
  const d = chart.data;
  if (!d) return false;
  // Array-based charts (bar, donut, line, table, word_cloud, horizontal_bar)
  if (Array.isArray(d)) return d.length > 0;
  // Driver table
  if (chart.visualization === "driver_table") return d.factors?.length > 0;
  return true;
};

/* ═══════════════════════════════════════════
   Generic chart renderer — no business logic
   ═══════════════════════════════════════════ */
const ChartCard: React.FC<{ chart: any }> = ({ chart }) => {
  const vis = chart.visualization;

  // Driver table — full width
  if (vis === "driver_table") {
    const d = chart.data;
    return (
      <div className={s.cardFull}>
        <div className={s.cardTitle}>{chart.title}</div>
        {chart.description && <div className={s.cardDesc}>{chart.description}</div>}
        <table className={s.driverTable}>
          <thead>
            <tr><th>Dimension</th><th>Value</th><th>{d.outcome_label || "Rate"}</th><th>vs Baseline ({d.baseline}%)</th><th>Count</th></tr>
          </thead>
          <tbody>
            {d.factors.map((f: any, j: number) => (
              <tr key={j}>
                <td style={{ color: "#64748b", fontSize: 11 }}>{f.dimension}</td>
                <td><strong>{f.value}</strong></td>
                <td>{f.rate}%</td>
                <td>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div className={s.driverBar}>
                      <div className={s.driverBarFill} style={{
                        width: `${Math.min(100, f.rate)}%`,
                        background: f.impact === "positive" ? "#059669" : "#dc2626",
                      }} />
                    </div>
                    <span className={f.impact === "positive" ? s.driverUp : s.driverDown}>
                      {f.deviation > 0 ? "+" : ""}{f.deviation}%
                    </span>
                  </div>
                </td>
                <td style={{ color: "#94a3b8" }}>{f.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // All other chart types
  return (
    <div className={s.card}>
      <div className={s.cardTitle}>{chart.title}</div>
      {chart.description && <div className={s.cardDesc}>{chart.description}</div>}

      {vis === "donut" && <DonutChart data={chart.data} height={260} />}
      {vis === "bar" && <BarChart data={chart.data} height={260} color="#2563eb" />}
      {vis === "horizontal_bar" && <BarChart data={chart.data} height={260} horizontal color="#1e3a6b" />}
      {vis === "line" && <LineChart data={chart.data} height={260} color="#2563eb" />}

      {vis === "table" && (
        <table className={s.topicTable}>
          <thead><tr><th>Item</th><th>Count</th></tr></thead>
          <tbody>
            {chart.data.map((d: any, j: number) => (
              <tr key={j}><td>{d.label}</td><td><strong>{d.value}</strong></td></tr>
            ))}
          </tbody>
        </table>
      )}

      {vis === "word_cloud" && (
        <div className={s.wordCloud}>
          {chart.data.map((p: any, i: number) => (
            <span key={i} className={s.wordItem}
              style={{ fontSize: Math.max(11, Math.round(p.weight * 14 + 10)),
                       color: WORD_COLORS[i % WORD_COLORS.length] }}
              title={`${p.text}: ${p.frequency}`}>{p.text}</span>
          ))}
        </div>
      )}
    </div>
  );
};

export default Insights;
