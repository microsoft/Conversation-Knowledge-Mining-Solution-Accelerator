import React, { useState, useEffect } from "react";
import { Button, Spinner, Dropdown, Option } from "@fluentui/react-components";
import { ArrowSync24Regular, ChartMultiple24Regular, ErrorCircle24Regular } from "@fluentui/react-icons";
import { DonutChart, BarChart, LineChart } from "../components/Charts";
import { useNavigate } from "react-router-dom";
import { getDashboard } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import type { DashboardResponse, KPI, ChartSpec } from "../types/api";
import { SkeletonCards } from "../components/Skeleton";
import s from "./Insights.module.css";

const WORD_COLORS = ["#2563eb", "#7c3aed", "#059669", "#dc2626", "#f59e0b", "#ec4899", "#0ea5e9", "#f97316"];

const Insights: React.FC = () => {
  const nav = useNavigate();
  const { setDashboardHeadline, insights: cachedData, setInsights } = useAppState();
  const [data, setData] = useState<DashboardResponse | null>(cachedData);
  const [loading, setLoading] = useState(!cachedData);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = async (f?: Record<string, string>, refresh = false) => {
    setLoading(true);
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
      console.error("Failed to load dashboard:", e);
      setError("Failed to load dashboard. Please try again.");
    }
    finally { setLoading(false); }
  };

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

  if (loading && !data) return (
    <div className={s.page}><div className={s.loading}>
      <Spinner size="medium" />
      <h3 style={{ margin: 0, color: "#475569", fontWeight: 600 }}>Analyzing your data...</h3>
      <p style={{ margin: 0, fontSize: 13, color: "#94a3b8" }}>Generating insights and visualizations</p>
      <SkeletonCards count={6} />
    </div></div>
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

  const ctx = data.data_context || {};
  const sections = data.sections || [];
  const kpis = data.kpis || [];
  const availableFilters = data.filters || [];
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
      <div className={s.content}>
        {/* ── Dataset header ── */}
        <div className={s.datasetHeader}>
          <div style={{ flex: 1 }}>
            <div className={s.datasetTitle}>{data.headline || "Data Insights"}</div>
            <div className={s.datasetMeta}>
              {ctx.total_records?.toLocaleString()} records
              {data.summary && <> &middot; {data.summary}</>}
              {ctx.filtered_records !== undefined && ctx.filtered_records !== ctx.total_records && (
                <span> &middot; Showing {ctx.filtered_records.toLocaleString()} filtered</span>
              )}
            </div>
          </div>
          <Button appearance="subtle" size="small" icon={<ArrowSync24Regular />}
            onClick={() => load(filters, true)} disabled={loading}>
            {loading ? "Analyzing..." : "Re-generate"}
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
          <div className={s.filterRow}>
            {availableFilters.map((f: any) => (
              <Dropdown key={f.field} placeholder={f.label}
                value={filters[f.field] || "All"}
                onOptionSelect={(_, opt) => applyFilter(f.field, opt?.optionValue || "")}
                size="small" style={{ minWidth: 140 }}>
                <Option value="_all" text={`All ${f.label}`}>All {f.label}</Option>
                {f.values.map((v: string) => <Option key={v} value={v} text={v}>{v}</Option>)}
              </Dropdown>
            ))}
            {Object.keys(filters).length > 0 && (
              <Button size="small" appearance="subtle" onClick={() => { setFilters({}); load({}); }}>Clear</Button>
            )}
          </div>
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
            {gridCharts.map((chart: any, i: number) => {
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
            <tr><th>Dimension</th><th>Value</th><th>Rate</th><th>vs Baseline ({d.baseline}%)</th><th>Count</th></tr>
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
