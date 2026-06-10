import React, { useState, useEffect, useRef } from "react";
import { Text, Badge, Spinner, Caption1, Button } from "@fluentui/react-components";
import {
  Send24Regular, Sparkle20Regular, Add20Regular, Chat20Regular,
  Database20Regular, DocumentText20Regular, Delete20Regular,
  ChevronDown20Regular, ChevronRight20Regular, Dismiss12Regular,
  Checkmark20Regular, ArrowUpload24Regular,
} from "@fluentui/react-icons";
import { askQuestion, getUploadedFiles, getExtractionInfo, listDataSources,
  saveChatHistory, listChatSessions, loadChatHistory, deleteChatSession } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import { useSearchParams, useLocation, useNavigate } from "react-router-dom";
import { DonutChart, BarChart } from "../components/Charts";
import { renderMarkdown } from "../utils/markdown";
import { SkeletonText, SkeletonChat } from "../components/Skeleton";
import s from "./Explore.module.css";

/* ── Chat content renderer ── */
const ChatContent: React.FC<{ content: string }> = ({ content }) => {
  const parts = content.split(/(```chart[\s\S]*?```)/g);
  return (
    <>
      {parts.map((part, i) => {
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

/* ── Component ── */
const Explore: React.FC = () => {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();

  // Data context
  const { exploreChatMessages, setExploreChatMessages, exploreData, setExploreData } = useAppState();
  const [files, setFiles] = useState<any[]>(exploreData?.files ?? []);
  const [dataSources, setDataSources] = useState<any[]>(exploreData?.dataSources ?? []);
  const [schema, setSchema] = useState<any>(exploreData?.schema ?? null);
  const [loading, setLoading] = useState(!exploreData);

  // Selection & filters
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [expandedDims, setExpandedDims] = useState<Set<string>>(new Set());

  // Chat
  const messages = exploreChatMessages;
  const setMessages = setExploreChatMessages;
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());
  const [lastSources, setLastSources] = useState<any[]>([]);

  // Sessions
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    if (!exploreData) loadData();
    loadSessions();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [fR, dR, sR] = await Promise.allSettled([
        getUploadedFiles(), listDataSources(), getExtractionInfo(),
      ]);
      const newFiles = fR.status === "fulfilled" ? fR.value.data.filter((f: any) => f.status === "ready" || !f.status) : [];
      const newDS = dR.status === "fulfilled" ? dR.value.data.filter((ds: any) => ds.status === "connected") : [];
      const newSchema = sR.status === "fulfilled" ? sR.value.data : null;
      setFiles(newFiles);
      setDataSources(newDS);
      if (newSchema) setSchema(newSchema);
      setExploreData({ files: newFiles, dataSources: newDS, schema: newSchema });
    } catch (e) { /* silently ignore */ } finally { setLoading(false); }
  };

  const loadSessions = () => {
    listChatSessions().then(r => setSessions(r.data?.sessions || r.data || [])).catch(() => {});
  };

  useEffect(() => {
    const q = searchParams.get("q");
    if (q && messages.length === 0) handleChat(q);
  }, [searchParams]);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleChat = async (text?: string) => {
    const q = text || chatInput;
    if (!q.trim() || chatLoading) return;
    const userMsg = { role: "user" as const, content: q };
    setMessages(prev => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);
    try {
      const docIds = selectedDocIds.size > 0 ? Array.from(selectedDocIds) : undefined;
      const scope = docIds ? "documents" as const : "all" as const;
      const filters = Object.keys(activeFilters).length > 0 ? activeFilters : undefined;
      const res = await askQuestion(q, 5, filters, scope, docIds);
      const asstMsg = { role: "assistant" as const, content: res.data.answer, sources: res.data.sources };
      setMessages(prev => [...prev, asstMsg]);
      if (res.data.sources?.length) setLastSources(res.data.sources);
      const allMsgs = [...messages, userMsg, asstMsg];
      const title = messages.length === 0 ? q.slice(0, 60) : undefined;
      saveChatHistory(sessionId, allMsgs, "default", title).then(() => loadSessions()).catch(() => {});
    } catch (err: unknown) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Unknown"}` }]);
    } finally { setChatLoading(false); }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocIds(prev => { const n = new Set(prev); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleFilter = (dim: string, value: string) => {
    setActiveFilters(prev => { const next = { ...prev }; next[dim] === value ? delete next[dim] : next[dim] = value; return next; });
  };
  const toggleDim = (id: string) => {
    setExpandedDims(p => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };
  const toggleSource = (idx: number) => {
    setExpandedSources(prev => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  };
  const startNew = () => { setSessionId(crypto.randomUUID()); setMessages([]); setExpandedSources(new Set()); setLastSources([]); };
  const loadSession = async (sid: string) => {
    try {
      const r = await loadChatHistory(sid);
      setSessionId(sid);
      setMessages((r.data?.messages || r.data || []).map((m: any) => ({ role: m.role, content: m.content, sources: m.sources })));
      setShowHistory(false);
    } catch (e) { /* silently ignore */ }
  };

  const totalRecords = files.reduce((sum, f) => sum + (f.doc_count || 0), 0) + dataSources.reduce((sum, d) => sum + (d.doc_count || 0), 0);
  const sessionCount = sessions.filter(sess => sess.message_count > 0).length;
  const scopeLabel = selectedDocIds.size > 0
    ? `${selectedDocIds.size} selected`
    : `${files.length + dataSources.length} source${files.length + dataSources.length !== 1 ? "s" : ""}`;

  return (
    <div className={s.page}>
      {/* ═══ CONTEXT BAR ═══ */}
      <div className={s.contextBar}>
        <DocumentText20Regular style={{ color: "#2563eb", fontSize: 16 }} />
        <span className={s.contextValue}>{totalRecords.toLocaleString()}</span> records
        <div className={s.contextSep} />
        <span>{scopeLabel}</span>
        {Object.keys(activeFilters).length > 0 && (
          <>
            <div className={s.contextSep} />
            {Object.entries(activeFilters).map(([k, v]) => (
              <span key={k} className={s.filterChip}>
                {k.replace("_", " ")}: {v}
                <button className={s.filterX} onClick={() => toggleFilter(k, v)}><Dismiss12Regular /></button>
              </span>
            ))}
          </>
        )}
        <span style={{ marginLeft: "auto" }} />
        <button onClick={() => setShowHistory(true)}
          style={{ border: "none", background: "none", cursor: "pointer", fontSize: 12, color: "#64748b",
            display: "flex", alignItems: "center", gap: 4, fontFamily: "inherit" }}>
          <Chat20Regular style={{ fontSize: 14 }} />
          History{sessionCount > 0 ? ` (${sessionCount})` : ""}
        </button>
      </div>

      <div className={s.body}>
        {/* ═══ LEFT: Data ═══ */}
        <div className={s.left}>
          <div className={s.leftSection}>
            <div className={s.leftLabel}>Data</div>
            {files.map(f => (
              <div key={f.id} className={selectedDocIds.has(f.id) ? s.sourceItemActive : s.sourceItem}
                onClick={() => toggleDoc(f.id)}>
                {selectedDocIds.has(f.id)
                  ? <Checkmark20Regular style={{ fontSize: 14, flexShrink: 0 }} />
                  : <DocumentText20Regular style={{ fontSize: 14, color: "#94a3b8", flexShrink: 0 }} />}
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.filename}</span>
                <Caption1>{f.doc_count}</Caption1>
              </div>
            ))}
            {dataSources.map(ds => (
              <div key={ds.id} className={s.sourceItem}>
                <Database20Regular style={{ fontSize: 14, color: "#f59e0b", flexShrink: 0 }} />
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ds.name}</span>
                <Caption1>{ds.doc_count?.toLocaleString()}</Caption1>
              </div>
            ))}
            {loading ? (
              <SkeletonText lines={4} />
            ) : files.length === 0 && dataSources.length === 0 ? (
              <div style={{ fontSize: 12, color: "#64748b", textAlign: "center", padding: "12px 0" }}>
                <p style={{ margin: "0 0 8px" }}>No data loaded yet</p>
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
            {selectedDocIds.size > 0 && (
              <button onClick={() => setSelectedDocIds(new Set())}
                style={{ border: "none", background: "none", cursor: "pointer", fontSize: 11,
                  color: "#2563eb", fontFamily: "inherit", padding: "4px 0", marginTop: 4 }}>
                Clear selection (chat with all)
              </button>
            )}
          </div>

          {schema?.dimensions?.length > 0 && (
            <div className={s.leftSection}>
              <div className={s.leftLabel}>Filters</div>
              {schema.dimensions.map((dim: any) => {
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
                <Sparkle20Regular style={{ fontSize: 36, color: "#cbd5e1" }} />
                <Text size={500} weight="semibold" style={{ color: "#0f172a" }}>Ask your data</Text>
                <Text size={300} style={{ color: "#64748b" }}>
                  Charts, summaries, trends, and analysis — all through conversation.
                </Text>
                <div className={s.suggestions}>
                  {PROMPTS.map(p => (
                    <button key={p} className={s.suggestionBtn} onClick={() => handleChat(p)}>{p}</button>
                  ))}
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, i) =>
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
                        <style>{`@keyframes pulse { 0%,100% { opacity:.3 } 50% { opacity:1 } }`}</style>
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
                <Add20Regular />
              </button>
              <textarea placeholder="Ask a question..." value={chatInput} rows={1}
                onChange={e => { setChatInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px"; }}
                onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
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
                <Dismiss12Regular />
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1 }}>
              <div className={s.histItem} onClick={() => { startNew(); setShowHistory(false); }}
                style={{ color: "#2563eb", fontWeight: 600 }}>
                <Add20Regular /> New conversation
              </div>
              {sessions.filter(sess => sess.message_count > 0).map(sess => (
                <div key={sess.id} className={s.histItem} onClick={() => loadSession(sess.id)}>
                  <Chat20Regular style={{ color: "#94a3b8", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {sess.title || "Untitled"}
                    </div>
                    <div style={{ color: "#94a3b8", fontSize: 11 }}>{sess.message_count} messages</div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); deleteChatSession(sess.id).then(() => loadSessions()); }}
                    style={{ border: "none", background: "none", cursor: "pointer", color: "#cbd5e1", padding: 2 }}>
                    <Delete20Regular />
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
