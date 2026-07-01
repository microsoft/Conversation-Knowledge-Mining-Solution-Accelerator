import React, { useState, useEffect, useRef } from "react";
import { Text, Caption1, Button } from "@fluentui/react-components";
import {
  Send24Regular, Sparkle24Regular, Add24Regular, Chat24Regular,
  Database24Regular, DocumentText24Regular, Delete24Regular,
  ChevronDown20Regular, ChevronRight20Regular,
  Checkmark24Regular, ArrowUpload24Regular,
} from "@fluentui/react-icons";
import { askQuestion, getUploadedFiles, getExtractionInfo, listDataSources,
  saveChatHistory, listChatSessions, loadChatHistory, deleteChatSession, refreshIngestionCache } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import { useSearchParams, useNavigate } from "react-router-dom";
import { DonutChart, BarChart } from "../components/Charts";
import { renderMarkdown } from "../utils/markdown";
import { SkeletonText, SkeletonChat } from "../components/Skeleton";
import s from "./Explore.module.css";

/* ── Chat content renderer ── */
const ChatContent: React.FC<{ content: string }> = ({ content }: { content: string }) => {
  const parts = content.split(/(```chart[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part: string, i: number) => {
        if (part.startsWith("```chart")) {
          try {
            const json = part.replace(/```chart\s*/, "").replace(/```$/, "");
            const spec = JSON.parse(json);
            if (spec.type === "donut") return <DonutChart key={i} data={spec.data} height={200} />;
            if (spec.type === "bar") return <BarChart key={i} data={spec.data} height={200} />;
          } catch {}
        }
        return <React.Fragment key={i}>{renderMarkdown(part)}</React.Fragment>;
      })}
    </>
  );
};

const PROMPTS = [
  "What are the key findings?",
  "Identify trends and patterns",
  "What are the main topics?",
  "What risks or issues exist?",
  "Summarize the data",
];

/* ── Source display helpers ── */
const getSourceLabel = (src: any, index: number): string => {
  const file = src.source_file || src.metadata?.source_file;
  if (file) {
    const name = file.split(/[/\\]/).pop() || file;
    return name;
  }
  if (src.title) return src.title;
  return `Source ${index + 1}`;
};

const getSourceSnippet = (text: string, maxLen = 120): string => {
  if (!text) return "";
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= maxLen) return clean;
  return clean.slice(0, maxLen).replace(/\s\S*$/, "") + "…";
};

const isFileSelectable = (status?: string): boolean => status === "ready" || status === "extracted" || !status;

const getFileStatusText = (status?: string): string | null => {
  if (status === "processing") return "Processing";
  if (status === "extracted") return "Chat ready";
  if (status === "failed") return "Failed";
  return null;
};

const getFileStatusColor = (status?: string): string | undefined => {
  if (status === "processing") return "#f59e0b";
  if (status === "extracted") return "#2563eb";
  if (status === "failed") return "#dc2626";
  return undefined;
};

const FILTER_BLOCKLIST = new Set(["page_count", "pagecount", "pages", "page"]);

/* ── Component ── */
const Explore: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // Data context
  const { exploreChatMessages, setExploreChatMessages, exploreData, setExploreData, ingestionSnapshot } = useAppState();
  const [files, setFiles] = useState<any[]>(exploreData?.files ?? []);
  const [dataSources, setDataSources] = useState<any[]>(exploreData?.dataSources ?? []);
  const [schema, setSchema] = useState<any>(exploreData?.schema ?? null);
  // Only show spinner on first ever load (no cached data). Background refresh on subsequent mounts.
  const [loading, setLoading] = useState(!exploreData);

  // Selection & filters
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [expandedDims, setExpandedDims] = useState<Set<string>>(new Set());
  const [sourcesExpanded, setSourcesExpanded] = useState(true);

  // Chat
  const messages = exploreChatMessages;
  const setMessages = setExploreChatMessages;
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());
  const [lastSources, setLastSources] = useState<any[]>([]);
  const processedAutoQueryRef = useRef<string>("");

  // Sessions
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const refreshedCacheRef = useRef(false);

  useEffect(() => {
    // Always refresh on mount to avoid stale cached empty state.
    loadData();
    loadSessions();
  }, []);

  const loadData = async () => {
    // Show spinner only if there is no data to display yet.
    if (!exploreData && files.length === 0) setLoading(true);
    try {
      // Refresh backend in-memory cache once per mount so seeded data is visible.
      if (!refreshedCacheRef.current) {
        try {
          await refreshIngestionCache();
        } catch {
          // Non-fatal: continue with normal reads.
        }
        refreshedCacheRef.current = true;
      }

      // During processing, only fetch files; skip data-sources and schema to reduce traffic
      const hasProcessing = files.some((f: any) => f.status === "processing");
      const requests: any[] = [getUploadedFiles()];
      if (!hasProcessing) {
        requests.push(listDataSources(), getExtractionInfo());
      } else {
        requests.push(Promise.resolve({ data: dataSources }) as any, Promise.resolve({ data: schema }) as any);
      }
      const [fR, dR, sR] = await Promise.allSettled(requests);
      const rawFiles = fR.status === "fulfilled" && Array.isArray(fR.value.data) ? fR.value.data : [];
      const newFiles = rawFiles;
      const rawDS = dR.status === "fulfilled" && Array.isArray(dR.value.data) ? dR.value.data : dataSources;
      const newDS = rawDS.filter((ds: any) => ds.status === "connected");
      const newSchema = sR.status === "fulfilled" ? sR.value.data : schema;
      setFiles(newFiles);
      setDataSources(newDS);
      if (newSchema) setSchema(newSchema);
      setExploreData({ files: newFiles, dataSources: newDS, schema: newSchema });
    } catch (e) {
      // Prefer empty state over stale cross-scenario data when requests fail.
      setFiles([]);
      setDataSources([]);
      setExploreData({ files: [], dataSources: [], schema });
    } finally { setLoading(false); }
  };

  const loadSessions = () => {
    listChatSessions().then((r: any) => {
      const raw = r.data?.sessions || r.data;
      setSessions(Array.isArray(raw) ? raw : []);
    }).catch(() => {});
  };

  useEffect(() => {
    const rawQ = searchParams.get("q") || "";
    const q = rawQ.trim();
    if (!q || chatLoading) return;

    const source = (searchParams.get("source") || "").toLowerCase();
    const fromInsights = source === "insights";
    const autoKey = `${source}|${q}`;

    if (processedAutoQueryRef.current === autoKey) return;
    if (!fromInsights && messages.length > 0) return;

    processedAutoQueryRef.current = autoKey;
    void handleChat(q, { resetConversation: fromInsights });
  }, [searchParams, messages.length, chatLoading]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    if (!ingestionSnapshot) return;
    const nextFiles = Array.isArray(ingestionSnapshot.uploadedFiles) ? ingestionSnapshot.uploadedFiles : [];
    const nextSources = Array.isArray(ingestionSnapshot.dataSources) ? ingestionSnapshot.dataSources.filter((ds: any) => ds.status === "connected") : [];
    const nextSchema = ingestionSnapshot.schema ?? schema;
    setFiles(nextFiles);
    setDataSources(nextSources);
    setSchema(nextSchema);
    setExploreData({ files: nextFiles, dataSources: nextSources, schema: nextSchema });
  }, [ingestionSnapshot]);

  const handleChat = async (text?: string, options?: { resetConversation?: boolean }) => {
    const q = text || chatInput;
    if (!q.trim() || chatLoading) return;
    const resetConversation = !!options?.resetConversation;

    let activeSessionId = sessionId;
    let existingMessages = messages;

    if (resetConversation) {
      activeSessionId = crypto.randomUUID();
      existingMessages = [];
      setSessionId(activeSessionId);
      setMessages([]);
      setExpandedSources(new Set());
      setLastSources([]);
    }

    const userMsg = { role: "user" as const, content: q };
    if (resetConversation) {
      setMessages([userMsg]);
    } else {
      setMessages((prev: any[]) => [...prev, userMsg]);
    }
    setChatInput("");
    setChatLoading(true);
    try {
      const docIds = selectedDocIds.size > 0 ? Array.from(selectedDocIds) as string[] : undefined;
      const scope = docIds ? "documents" as const : "all" as const;
      const filters = Object.keys(activeFilters).length > 0 ? activeFilters : undefined;
      const res = await askQuestion(q, 5, filters, scope, docIds, activeSessionId);
      const asstMsg = { role: "assistant" as const, content: res.data.answer, sources: res.data.sources };
      setMessages((prev: any[]) => [...prev, asstMsg]);
      if (res.data.sources?.length) setLastSources(res.data.sources);
      const allMsgs = [...existingMessages, userMsg, asstMsg];
      const title = existingMessages.length === 0 ? q.slice(0, 60) : undefined;
      saveChatHistory(activeSessionId, allMsgs, "default", title).then(() => loadSessions()).catch(() => {});
    } catch (err: unknown) {
      setMessages((prev: any[]) => [...prev, { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Unknown"}` }]);
    } finally { setChatLoading(false); }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocIds((prev: Set<string>) => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleFilter = (dim: string, value: string) => {
    setActiveFilters((prev: Record<string, string>) => { const next = { ...prev }; next[dim] === value ? delete next[dim] : next[dim] = value; return next; });
  };
  const toggleDim = (id: string) => {
    setExpandedDims((p: Set<string>) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleSource = (idx: number) => {
    setExpandedSources((prev: Set<number>) => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  };
  const startNew = () => { setSessionId(crypto.randomUUID()); setMessages([]); setExpandedSources(new Set()); setLastSources([]); };
  const loadSession = async (sid: string) => {
    try {
      const r = await loadChatHistory(sid);
      setSessionId(sid);
      const rawMsgs = r.data?.messages || r.data;
      setMessages(Array.isArray(rawMsgs) ? rawMsgs.map((m: any) => ({ role: m.role, content: m.content, sources: m.sources })) : []);
      setShowHistory(false);
    } catch (e) { /* silently ignore */ }
  };

  const readyFiles = files.filter((f: any) => isFileSelectable(f.status));
  const sourceFileNames = new Set(
    readyFiles
      .map((f: any) => String(f.filename || "").toLowerCase())
      .filter(Boolean)
  );
  const visibleDimensions = Array.isArray(schema?.dimensions)
    ? schema.dimensions.filter((dim: any) => {
      const dimKey = String(dim?.id || dim?.label || "").toLowerCase().replace(/\s+/g, "_");
      if (FILTER_BLOCKLIST.has(dimKey)) return false;
      if (dimKey !== "source_file" && dimKey !== "sourcefile") return true;

      const dimValues = Array.isArray(dim?.values) ? dim.values : [];
      const normalizedValues = dimValues
        .map((v: any) => String(v?.value || v?.label || "").toLowerCase())
        .filter(Boolean);

      if (sourceFileNames.size === 0 || normalizedValues.length === 0) return true;

      const allValuesInSources = normalizedValues.every((v: string) => sourceFileNames.has(v));
      return !allValuesInSources;
    })
    : [];
  const totalRecords = readyFiles.reduce((sum: number, f: any) => sum + (f.doc_count || 0), 0) + dataSources.reduce((sum: number, d: any) => sum + (d.doc_count || 0), 0);
  const sessionCount = sessions.filter((sess: any) => sess.message_count > 0).length;
  const scopeLabel = selectedDocIds.size > 0
    ? `${selectedDocIds.size} selected`
    : `${readyFiles.length + dataSources.length} ready source${readyFiles.length + dataSources.length !== 1 ? "s" : ""}`;

  return (
    <div className={s.page}>
      {/* ═══ CONTEXT BAR ═══ */}
      <div className={s.contextBar}>
        <DocumentText24Regular style={{ color: "#2563eb", fontSize: 16 }} />
        <span className={s.contextValue}>{totalRecords.toLocaleString()}</span> records
        <div className={s.contextSep} />
        <span>{scopeLabel}</span>
        {Object.keys(activeFilters).length > 0 && (
          <>
            <div className={s.contextSep} />
            {Object.entries(activeFilters).map(([k, v]) => (
              <span key={k} className={s.filterChip}>
                {k.replace("_", " ")}: {v}
                <button className={s.filterX} onClick={() => toggleFilter(k as string, v as string)} aria-label="Remove filter">x</button>
              </span>
            ))}
          </>
        )}
        <span style={{ marginLeft: "auto" }} />
        <button onClick={() => setShowHistory(true)}
          style={{ border: "none", background: "none", cursor: "pointer", fontSize: 12, color: "#64748b",
            display: "flex", alignItems: "center", gap: 4, fontFamily: "inherit" }}>
          <Chat24Regular style={{ fontSize: 14 }} />
          History{sessionCount > 0 ? ` (${sessionCount})` : ""}
        </button>
      </div>

      <div className={s.body}>
        {/* ═══ LEFT: Data ═══ */}
        <div className={s.left}>
          <div className={s.leftSection}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <button
                className={s.sectionToggle}
                onClick={() => setSourcesExpanded((prev) => !prev)}
                title="Expand or collapse sources"
              >
                {sourcesExpanded ? <ChevronDown20Regular style={{ fontSize: 14 }} /> : <ChevronRight20Regular style={{ fontSize: 14 }} />}
                <span className={s.leftLabel} style={{ marginBottom: 0 }}>Sources</span>
              </button>
              {selectedDocIds.size > 0 && (
                <button onClick={() => setSelectedDocIds(new Set())}
                  title="Clear selection"
                  style={{
                    display: "flex", alignItems: "center", gap: 3,
                    border: "none", borderRadius: 4, background: "none",
                    cursor: "pointer", fontSize: 11, color: "#64748b",
                    fontFamily: "inherit", padding: "2px 4px",
                    transition: "color 0.15s",
                  }}
                  onMouseEnter={(e: React.MouseEvent<HTMLButtonElement>) => (e.currentTarget.style.color = "#2563eb")}
                  onMouseLeave={(e: React.MouseEvent<HTMLButtonElement>) => (e.currentTarget.style.color = "#64748b")}>
                  x
                </button>
              )}
            </div>
            {sourcesExpanded && files.map((f: any) => {
              const isReady = isFileSelectable(f.status);
              const statusText = getFileStatusText(f.status);
              return (
                <div key={f.id} className={selectedDocIds.has(f.id) ? s.sourceItemActive : s.sourceItem}
                  onClick={() => isReady && toggleDoc(f.id)}
                  style={!isReady ? { opacity: 0.65, cursor: "default" } : undefined}>
                  {selectedDocIds.has(f.id)
                    ? <Checkmark24Regular style={{ fontSize: 14, flexShrink: 0 }} />
                    : <DocumentText24Regular style={{ fontSize: 14, color: "#94a3b8", flexShrink: 0 }} />}
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.filename}</span>
                  {statusText && <Caption1 style={{ color: getFileStatusColor(f.status) }}>{statusText}</Caption1>}
                  {isReady && <Caption1>{f.doc_count || 1}</Caption1>}
                </div>
              );
            })}
            {sourcesExpanded && dataSources.map((ds: any) => (
              <div key={ds.id} className={s.sourceItem}>
                <Database24Regular style={{ fontSize: 14, color: "#f59e0b", flexShrink: 0 }} />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ds.name}</span>
                <Caption1>{ds.doc_count?.toLocaleString()}</Caption1>
              </div>
            ))}
            {sourcesExpanded && loading ? (
              <SkeletonText lines={4} />
            ) : sourcesExpanded && files.length === 0 && dataSources.length === 0 ? (
              <div style={{ fontSize: 12, color: "#64748b", textAlign: "center", padding: "12px 0" }}>
                <p style={{ margin: "0 0 8px" }}>No data loaded yet</p>
                <p style={{ margin: "0 0 10px", color: "#94a3b8" }}>
                  If a scenario is loading, sources will appear here automatically.
                </p>
                <Button
                  size="small"
                  appearance="primary"
                  icon={<ArrowUpload24Regular />}
                  onClick={() => navigate("/")}
                >
                  Upload data
                </Button>
              </div>
            ) : null}

            {!sourcesExpanded && (
              <Caption1 style={{ color: "#64748b" }}>
                {files.length + dataSources.length} sources hidden
              </Caption1>
            )}

          </div>

          {visibleDimensions.length > 0 && (
            <div className={s.leftSection}>
              <div className={s.leftLabel} title="Use these to narrow records before asking questions">Filter dimensions</div>
              {visibleDimensions.map((dim: any) => {
                const expanded = expandedDims.has(dim.id);
                return (
                  <div key={dim.id} className={s.filterGroup}>
                    <button className={s.filterBtn} onClick={() => toggleDim(dim.id)}>
                      <ChevronRight20Regular style={{ fontSize: 14, transform: expanded ? "rotate(90deg)" : "none", transition: "transform 0.15s" }} />
                      {dim.label}
                    </button>
                    {expanded && dim.values?.map((v: any) => (
                      <button key={v.value}
                        className={activeFilters[dim.id] === v.value ? s.filterValueActive : s.filterValue}
                        onClick={() => toggleFilter(dim.id, v.value)}>
                        <span style={{ flex: 1 }}>{v.label}</span>
                        <Caption1>{v.count}</Caption1>
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ═══ CENTER: Chat ═══ */}
        <div className={s.center}>
          <div className={s.chatMessages}>
            {messages.length === 0 ? (
              <div className={s.emptyChat}>
                <Sparkle24Regular style={{ fontSize: 36, color: "#cbd5e1" }} />
                <Text size={500} weight="semibold" style={{ color: "#0f172a" }}>Ask your data</Text>
                <Text size={300} style={{ color: "#64748b" }}>
                  Charts, summaries, trends, and analysis — all through conversation.
                </Text>
                <div className={s.suggestions}>
                  {PROMPTS.map((p: string) => (
                    <button key={p} className={s.suggestionBtn} onClick={() => handleChat(p)}>{p}</button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg: any, i: number) =>
                  msg.role === "user" ? (
                    <div key={i} className={s.userMsg}><ChatContent content={msg.content} /></div>
                  ) : (
                    <div key={i} className={s.assistantWrap}>
                      <div className={s.assistantMsg}><ChatContent content={msg.content} /></div>
                      {(msg.sources?.length ?? 0) > 0 && (
                        <>
                          <button className={s.evidenceToggle} onClick={() => toggleSource(i)}>
                            {expandedSources.has(i) ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
                            {(msg.sources || []).length} source{(msg.sources || []).length !== 1 ? "s" : ""} used
                          </button>
                          {expandedSources.has(i) && (
                            <div className={s.evidenceList}>
                              {(msg.sources || []).map((src: any, j: number) => (
                                <div key={j} className={s.evidenceItem}>
                                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                                    <span style={{ fontWeight: 600, color: "#0f172a" }} title={src.doc_id}>{getSourceLabel(src, j)}</span>
                                    <span style={{ color: "#2563eb", fontWeight: 600, fontSize: 11 }}>{(src.score * 100).toFixed(0)}%</span>
                                  </div>
                                  {src.text && <div style={{ color: "#64748b", marginTop: 2, fontSize: 11, lineHeight: 1.4 }}>{getSourceSnippet(src.text, 180)}</div>}
                                </div>
                              ))}
                            </div>
                          )}
                        </>
                      )}
                      <div className={s.disclaimer}>AI-generated content may be incorrect</div>
                    </div>
                  )
                )}
                {chatLoading && (
                  <div className={s.assistantWrap}>
                    <div className={s.assistantMsg}>
                      <span style={{ color: "#9ca3af" }}>
                        <span style={{ animation: "pulse 1.5s ease-in-out infinite" }}>●</span>{" "}
                        <span style={{ animation: "pulse 1.5s ease-in-out 0.3s infinite" }}>●</span>{" "}
                        <span style={{ animation: "pulse 1.5s ease-in-out 0.6s infinite" }}>●</span>
                      </span>
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </>
            )}
          </div>

          <div className={s.inputWrap}>
            <div className={s.inputBox}>
              <button onClick={startNew} title="New conversation"
                style={{ border: "none", background: "none", cursor: "pointer", padding: 4,
                  display: "flex", color: "#6366f1", marginTop: 2, flexShrink: 0 }}>
                <Add24Regular />
              </button>
              <textarea placeholder="Ask a question..." value={chatInput} rows={1}
                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => { setChatInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px"; }}
                onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
                style={{ flex: 1, border: "none", outline: "none", fontSize: 14, background: "transparent",
                  color: "#1f2937", fontFamily: "inherit", resize: "none", overflow: "auto",
                  lineHeight: 1.5, maxHeight: 150, minHeight: 24 }}
              />
              <button onClick={() => handleChat()} disabled={chatLoading || !chatInput.trim()} title="Send"
                style={{ border: "none", background: "none", cursor: chatInput.trim() ? "pointer" : "default",
                  padding: 4, display: "flex", color: chatInput.trim() ? "#6366f1" : "#d1d5db", marginTop: 2, flexShrink: 0 }}>
                <Send24Regular />
              </button>
            </div>
          </div>
        </div>

        {/* Sources panel hidden — sources are already shown inline under each answer */}
      </div>

      {/* ═══ HISTORY DRAWER ═══ */}
      {showHistory && (
        <>
          <div className={s.overlay} onClick={() => setShowHistory(false)} />
          <div className={s.histDrawer}>
            <div className={s.histHeader}>
              Chat History
              <button onClick={() => setShowHistory(false)}
                style={{ border: "none", background: "none", cursor: "pointer", color: "#94a3b8" }}>
                x
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1 }}>
              <div className={s.histItem} onClick={() => { startNew(); setShowHistory(false); }}
                style={{ color: "#2563eb", fontWeight: 600 }}>
                <Add24Regular /> New conversation
              </div>
              {sessions.filter((sess: any) => sess.message_count > 0).map((sess: any) => (
                <div key={sess.id} className={s.histItem} onClick={() => loadSession(sess.id)}>
                  <Chat24Regular style={{ color: "#94a3b8", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {sess.title || "Untitled"}
                    </div>
                    <div style={{ color: "#94a3b8", fontSize: 11 }}>{sess.message_count} messages</div>
                  </div>
                  <button onClick={(e: React.MouseEvent<HTMLButtonElement>) => { e.stopPropagation(); deleteChatSession(sess.id).then(() => loadSessions()); }}
                    style={{ border: "none", background: "none", cursor: "pointer", color: "#cbd5e1", padding: 2 }}>
                    <Delete24Regular />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Explore;
