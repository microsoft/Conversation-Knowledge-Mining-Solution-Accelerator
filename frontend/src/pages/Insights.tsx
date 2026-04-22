import React, { useState, useEffect, useRef } from "react";
import { Button, Spinner, Badge, Dropdown, Option } from "@fluentui/react-components";
import {
  ArrowSync24Regular, Sparkle24Regular,
  Lightbulb24Regular, DataBarVertical24Regular,
  ArrowTrending24Regular, PeopleCommunity24Regular,
  ShieldError24Regular, Chat24Regular,
  ArrowDownload24Regular, Settings24Regular,
  ChevronRight20Regular,
} from "@fluentui/react-icons";
import { DonutChart, BarChart } from "../components/Charts";
import { useNavigate } from "react-router-dom";
import { getInsights, getUploadedFiles } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import s from "./Insights.module.css";

const CAT_COLORS: Record<string, string> = {
  pattern: "#2563eb", risk: "#f59e0b", opportunity: "#059669",
};
const SEV: Record<string, { bg: string; fg: string }> = {
  high: { bg: "#fee2e2", fg: "#dc2626" },
  medium: { bg: "#fef3c7", fg: "#d97706" },
  low: { bg: "#d1fae5", fg: "#059669" },
};

const Insights: React.FC = () => {
  const nav = useNavigate();
  const { insights: cached, setInsights: cache } = useAppState();
  const [data, setData] = useState<any>(cached);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("Analyzing your documents...");
  const [files, setFiles] = useState<Array<{ id: string; filename: string }>>([]);
  const [scope, setScope] = useState("all");
  const [open, setOpen] = useState<Set<string>>(new Set(["insights", "trends", "entities", "risks"]));
  const loadedRef = useRef(false);

  const go = (q: string) => nav(`/explore?q=${encodeURIComponent(q)}`);
  const toggle = (id: string) => setOpen((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const load = async (fileIds?: string[], docName?: string) => {
    setLoading(true);
    setLoadingMsg(docName ? `Analyzing "${docName}"...` : "Analyzing all documents...");
    setData(null); // Clear stale data so user sees fresh results
    try { const r = (await getInsights(fileIds)).data; setData(r); cache(r); } catch {}
    finally { setLoading(false); }
  };

  useEffect(() => {
    getUploadedFiles().then((r) => setFiles(r.data)).catch(() => {});
    if (!cached && !loadedRef.current) {
      loadedRef.current = true;
      load();
    }
  }, []);

  const handleScope = (_: any, opt: any) => {
    const v = opt.optionValue || "all";
    setScope(v);
    if (v === "all") {
      load(undefined, undefined);
    } else {
      const fileName = files.find((f) => f.id === v)?.filename || v;
      load([v], fileName);
    }
  };

  const exportData = () => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "insights-report.json"; a.click();
    URL.revokeObjectURL(url);
  };

  if (!data && !loading) return (
    <div className={s.page}><div className={s.empty}>
      <Sparkle24Regular style={{ fontSize: 48 }} /><h2>No insights yet</h2><p>Upload documents to generate intelligence.</p>
    </div></div>
  );
  if (loading && !data) return (
    <div className={s.page}><div className={s.loading}>
      <Spinner size="large" /><h3>{loadingMsg}</h3>
    </div></div>
  );

  const findings = data?.deep_findings || data?.key_insights || data?.key_findings || [];
  const signals = data?.signals || data?.signal_cards || [];
  const chains = data?.causal_chains || (data?.root_causes?.chains || []);
  const entities = data?.entity_map || data?.entity_intelligence?.top_entities || [];
  const risks = data?.risks || data?.risk_assessment?.risks || [];
  const opps = data?.opportunities || [];
  const questions = data?.questions_to_investigate || data?.suggested_questions || [];

  return (
    <div className={s.page}>
      {/* ── Sticky top bar ── */}
      <div className={s.topBar}>
        <div className={s.topTitle}>Insights Report</div>
        <div className={s.topRight}>
          <Dropdown
            value={scope === "all" ? "All Documents" : files.find((f) => f.id === scope)?.filename || scope}
            onOptionSelect={handleScope}
            size="small"
            style={{ minWidth: 180 }}
          >
            <Option value="all">All Documents</Option>
            {files.map((f) => <Option key={f.id} value={f.id}>{f.filename}</Option>)}
          </Dropdown>
          <Button appearance="primary" size="small" icon={<ArrowSync24Regular />}
            onClick={() => {
              if (scope === "all") load(undefined, undefined);
              else load([scope], files.find((f) => f.id === scope)?.filename || scope);
            }} disabled={loading}>
            {loading ? "Analyzing..." : "Refresh"}
          </Button>
          <Button appearance="subtle" size="small" icon={<ArrowDownload24Regular />} onClick={exportData}>
            Export
          </Button>
        </div>
      </div>

      <div className={s.content}>
        {/* ── Headline ── */}
        <div className={s.headline}>
          <div className={s.headlineText}>{data?.headline || "Analysis Complete"}</div>
          <div className={s.narrative}>
            {data?.narrative || data?.executive_summary?.text || data?.executive_summary || ""}
          </div>
          <div className={s.meta}>
            {data?.confidence && <span>Confidence: <strong>{data.confidence}</strong></span>}
            <span>{findings.length} findings</span>
            <span>{entities.length} entities</span>
            <span>{risks.length} risks</span>
          </div>
        </div>

        {/* ── 1. Metrics (always visible, no collapse) ── */}
        {signals.length > 0 && (
          <div className={s.metricsRow}>
            {signals.map((sig: any, i: number) => {
              const cat = sig.category || "pattern";
              return (
                <div key={i} className={s.metric} data-cat={cat}>
                  <div className={s.metricCat} style={{ color: CAT_COLORS[cat] || "#94a3b8" }}>{cat.toUpperCase()}</div>
                  <div className={s.metricValue}>{sig.metric || sig.value}</div>
                  <div className={s.metricLabel}>{sig.label || sig.title}</div>
                  <div className={s.metricDesc}>{sig.interpretation || sig.context}</div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── Charts ── */}
        {(entities.length > 0 || risks.length > 0) && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            {/* Entity relevance chart */}
            {entities.length > 0 && (
              <div className={s.section} style={{ padding: "20px 24px" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", marginBottom: 12 }}>Entity Relevance</div>
                <BarChart
                  data={entities.slice(0, 6).map((e: any) => ({ label: e.name, value: e.relevance || 50 }))}
                  height={180}
                  horizontal
                  color="#2563eb"
                />
              </div>
            )}

            {/* Risk distribution chart */}
            {risks.length > 0 && (
              <div className={s.section} style={{ padding: "20px 24px" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", marginBottom: 12 }}>Risk Distribution</div>
                <DonutChart
                  data={(() => {
                    const counts: Record<string, number> = {};
                    risks.forEach((r: any) => { const sev = r.severity || "medium"; counts[sev] = (counts[sev] || 0) + 1; });
                    return Object.entries(counts).map(([label, value]) => ({ label, value }));
                  })()}
                  height={180}
                />
              </div>
            )}
          </div>
        )}

        {/* ── 2. Key Insights (collapsible) ── */}
        {findings.length > 0 && (
          <Section id="insights" title="Key Insights" count={findings.length} open={open} toggle={toggle}
            icon={<Lightbulb24Regular />} iconBg="#dbeafe" iconColor="#2563eb"
            actions={[{ label: "Ask about this", fn: () => go("Explain the key findings") }, { label: "Export", fn: exportData }]}>
            {findings.map((f: any, i: number) => (
              <div key={i} className={s.insight}>
                <div className={s.insightFinding}>{typeof f === "string" ? f : f.finding || JSON.stringify(f)}</div>
                {f.why_it_matters && <div className={s.insightWhy}>{f.why_it_matters}</div>}
                {f.recommendation && <div className={s.insightRec}>→ {f.recommendation}</div>}
              </div>
            ))}
          </Section>
        )}

        {/* ── 3. Trends & Root Causes ── */}
        {chains.length > 0 && (
          <Section id="trends" title="Trends & Root Causes" count={chains.length} open={open} toggle={toggle}
            icon={<ArrowTrending24Regular />} iconBg="#fef3c7" iconColor="#d97706"
            actions={[{ label: "Ask about this", fn: () => go("Explain the trends and root causes") }]}>
            {chains.map((c: any, i: number) => (
              <div key={i} className={s.trend}>
                <div className={s.trendChain}>{typeof c === "string" ? c : c.chain || JSON.stringify(c)}</div>
                {typeof c === "object" && c.explanation && <div className={s.trendExplain}>{c.explanation}</div>}
              </div>
            ))}
          </Section>
        )}

        {/* ── 4. Entities & Themes ── */}
        {entities.length > 0 && (
          <Section id="entities" title="Entities & Themes" count={entities.length} open={open} toggle={toggle}
            icon={<PeopleCommunity24Regular />} iconBg="#dbeafe" iconColor="#2563eb"
            actions={[{ label: "Ask about this", fn: () => go("Tell me about the key entities") }]}>
            <div className={s.entityGrid}>
              {entities.map((e: any, i: number) => (
                <div key={i} className={s.entity} onClick={() => go(e.name)}>
                  <div className={s.entityName}>{e.name}</div>
                  <div className={s.entityRole}>{e.role || e.context || ""}</div>
                  <div className={s.entityBar}>
                    <div className={s.entityBarFill} style={{ width: `${e.relevance || 50}%` }} />
                  </div>
                  {e.connections?.length > 0 && (
                    <div className={s.entityTags}>
                      {e.connections.map((c: string) => <Badge key={c} appearance="outline" size="small" shape="rounded">{c}</Badge>)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ── 5. Risks & Opportunities ── */}
        {(risks.length > 0 || opps.length > 0) && (
          <Section id="risks" title="Risks & Opportunities" count={risks.length + opps.length} open={open} toggle={toggle}
            icon={<ShieldError24Regular />} iconBg="#fee2e2" iconColor="#dc2626"
            actions={[{ label: "Ask about this", fn: () => go("What are the risks and opportunities?") }, { label: "Refine", fn: () => {
              if (scope === "all") load(undefined, undefined);
              else load([scope], files.find((f) => f.id === scope)?.filename || scope);
            } }]}>
            <div className={s.riskOppGrid}>
              <div className={s.riskCol}>
                <div className={s.riskColLabel}>Risks ({risks.length})</div>
                {risks.map((r: any, i: number) => {
                  const sv = SEV[r.severity] || SEV.medium;
                  return (
                    <div key={i} className={s.risk}>
                      <div className={s.riskHeader}>
                        <span className={s.riskBadge} style={{ background: sv.bg, color: sv.fg }}>{r.severity}</span>
                        <span className={s.riskTitle}>{typeof r === "string" ? r : r.risk}</span>
                      </div>
                      {r.evidence && <div className={s.riskDetail}>Evidence: {r.evidence}</div>}
                      {r.mitigation && <div className={s.riskDetail} style={{ color: "#059669" }}>Mitigation: {r.mitigation}</div>}
                    </div>
                  );
                })}
              </div>
              <div className={s.oppCol}>
                <div className={s.oppColLabel}>Opportunities ({opps.length})</div>
                {opps.map((o: any, i: number) => (
                  <div key={i} className={s.opp}>
                    <div className={s.oppTitle}>{typeof o === "string" ? o : o.opportunity}</div>
                    {o.potential_impact && <div className={s.oppImpact}>Impact: {o.potential_impact}</div>}
                    {o.next_step && <div className={s.oppNext}>→ {o.next_step}</div>}
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ── 6. Investigate Further ── */}
        {questions.length > 0 && (
          <Section id="questions" title="Investigate Further" open={open} toggle={toggle}
            icon={<Chat24Regular />} iconBg="#d1fae5" iconColor="#059669">
            <div className={s.questionGrid}>
              {questions.map((q: string, i: number) => (
                <button key={i} className={s.questionBtn} onClick={() => go(q)}>{q}</button>
              ))}
            </div>
          </Section>
        )}


      </div>
    </div>
  );
};

/* ── Collapsible Section ── */
const Section: React.FC<{
  id: string;
  title: string;
  count?: number;
  open: Set<string>;
  toggle: (id: string) => void;
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  actions?: Array<{ label: string; fn: () => void }>;
  children: React.ReactNode;
}> = ({ id, title, count, open, toggle, icon, iconBg, iconColor, actions, children }) => {
  const isOpen = open.has(id);
  return (
    <div className={s.section}>
      <div className={s.sectionHeader} onClick={() => toggle(id)}>
        <div className={s.sectionIcon} style={{ background: iconBg, color: iconColor }}>{icon}</div>
        <div className={s.sectionTitle}>{title}</div>
        {count !== undefined && <div className={s.sectionCount}>{count}</div>}
        <ChevronRight20Regular className={isOpen ? s.sectionChevronOpen : s.sectionChevron} />
      </div>
      {isOpen && (
        <div className={s.sectionBody}>
          {children}
          {actions && actions.length > 0 && (
            <div className={s.sectionActions}>
              {actions.map((a) => (
                <button key={a.label} className={s.actionBtn} onClick={a.fn}>{a.label}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Insights;
