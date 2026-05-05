import React, { useState, useEffect } from "react";
import { Button, Spinner, Dropdown, Option } from "@fluentui/react-components";
import { ArrowSync24Regular, ChartMultiple24Regular, ChevronRight20Regular } from "@fluentui/react-icons";
import { DonutChart, BarChart, LineChart } from "../components/Charts";
import { useNavigate } from "react-router-dom";
import { getDashboard } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import s from "./Insights.module.css";

const WORD_COLORS = ["#2563eb", "#7c3aed", "#059669", "#dc2626", "#f59e0b", "#ec4899", "#0ea5e9", "#f97316"];

const Insights: React.FC = () => {
  const nav = useNavigate();
  const { setDashboardHeadline } = useAppState();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggle = (id: string) => setCollapsed(p => {
    const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n;
  });

  const load = async (f?: Record<string, string>, refresh = false) => {
    setLoading(true);
    try {
      const r = await getDashboard(f, refresh);
      setData(r.data);
      if (r.data?.headline) {
        setDashboardHeadline(r.data.headline);
        try { sessionStorage.setItem("km_headline", JSON.stringify(r.data.headline)); } catch {}
      }
    } catch (e) { console.error("Dashboard load failed", e); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const applyFilter = (field: string, value: string) => {
    const next = { ...filters };
    if (!value || value === "_all") delete next[field];
    else next[field] = value;
    setFilters(next);
    load(next);
  };

  const fmt = (kpi: any) => {
    if (kpi.format === "percentage") return `${kpi.value}%`;
    if (kpi.format === "minutes") return `${kpi.value}mins`;
    return kpi.value?.toLocaleString?.() ?? kpi.value;
  };

  if (loading && !data) return (
    <div className={s.page}><div className={s.loading}>
      <Spinner size="large" /><h3>Analyzing your data...</h3>
    </div></div>
  );

  if (!data || (data.data_context?.total_records ?? data.total_records ?? 0) === 0) return (
    <div className={s.page}><div className={s.empty}>
      <ChartMultiple24Regular style={{ fontSize: 48 }} />
      <h2>No Data Available</h2><p>Upload documents or connect a data source to see insights.</p>
    </div></div>
  );

  const ctx = data.data_context || {};
  const sections = data.sections || [];
  const kpis = data.kpis || [];
  const availableFilters = data.filters || [];
  const questions = data.suggested_questions || [];

  return (
    <div className={s.page}>
      <div className={s.content}>
        {/* ── Top: summary + record count + re-analyze ── */}
        <div className={s.topBar}>
          <div style={{ flex: 1 }}>
            {data.summary && <div className={s.summary}>{data.summary}</div>}
            {ctx.filtered_records !== undefined && ctx.filtered_records !== ctx.total_records && (
              <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
                Showing {ctx.filtered_records} of {ctx.total_records} records
              </div>
            )}
          </div>
          <Button appearance="subtle" size="small" icon={<ArrowSync24Regular />}
            onClick={() => load(filters, true)} disabled={loading}>
            {loading ? "Analyzing..." : "Re-analyze"}
          </Button>
        </div>

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

        {/* ── Sections — everything from backend, rendered generically ── */}
        {sections.map((sec: any) => (
          <Section key={sec.id} id={sec.id} title={sec.title}
            collapsed={collapsed} toggle={toggle}>
            <div className={sec.charts?.length === 1 ? undefined : s.chartGrid}>
              {(sec.charts || []).map((chart: any, ci: number) => (
                <ChartCard key={ci} chart={chart} />
              ))}
            </div>
          </Section>
        ))}

        {/* ── Suggested questions ── */}
        {questions.length > 0 && (
          <div className={s.card}>
            <div className={s.cardTitle}>Investigate Further</div>
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
              style={{ fontSize: Math.max(12, Math.round(p.weight * 32 + 10)),
                       color: WORD_COLORS[i % WORD_COLORS.length] }}
              title={`${p.text}: ${p.frequency}`}>{p.text}</span>
          ))}
        </div>
      )}
    </div>
  );
};

/* ═══════════════════════════════════════════
   Collapsible section
   ═══════════════════════════════════════════ */
const Section: React.FC<{
  id: string; title: string;
  collapsed: Set<string>; toggle: (id: string) => void;
  children: React.ReactNode;
}> = ({ id, title, collapsed, toggle, children }) => {
  const isOpen = !collapsed.has(id);
  return (
    <div className={s.section}>
      <div className={s.sectionHeader} onClick={() => toggle(id)}>
        <div className={s.sectionTitle}>{title}</div>
        <ChevronRight20Regular className={isOpen ? s.sectionChevronOpen : s.sectionChevron} />
      </div>
      {isOpen && <div className={s.sectionBody}>{children}</div>}
    </div>
  );
};

export default Insights;
