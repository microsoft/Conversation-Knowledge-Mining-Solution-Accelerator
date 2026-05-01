import React, { useState, useEffect, useRef } from "react";
import {
  makeStyles,
  tokens,
  Text,
  Input,
  Button,
  Spinner,
  Badge,
  Checkbox,
  Caption1,
} from "@fluentui/react-components";
import {
  Search24Regular,
  Send24Regular,
  Dismiss12Regular,
  Delete20Regular,
  DocumentText24Regular,
  ChevronRight20Regular,
  Filter20Regular,
  Sparkle20Regular,
  Database20Regular,
  PlugConnected20Regular,
  Add20Regular,
  Chat20Regular,
} from "@fluentui/react-icons";
import { askQuestion, getUploadedFiles, getExtractionInfo, listDataSources, saveChatHistory, listChatSessions, loadChatHistory, deleteChatSession } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import { useSearchParams } from "react-router-dom";
import { DonutChart, BarChart } from "../components/Charts";
import { renderMarkdown } from "../utils/markdown";

/* ── Styles ── */
const useStyles = makeStyles({
  page: {
    display: "flex",
    height: "100%",
    overflow: "hidden",
  },

  /* Left panel — filters only */
  left: {
    width: "240px",
    flexShrink: 0,
    borderRight: `1px solid #e5e7eb`,
    backgroundColor: "#ffffff",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
  },
  leftHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "16px 20px",
    fontWeight: 600,
    fontSize: "13px",
    color: "var(--km-text-primary)",
    borderBottom: `1px solid var(--km-border)`,
  },
  searchWrap: {
    padding: "12px 16px",
    borderBottom: `1px solid var(--km-border-light)`,
  },
  filterGroup: { padding: "0" },
  filterGroupBtn: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "10px 20px",
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--km-text-primary)",
    cursor: "pointer",
    border: "none",
    backgroundColor: "transparent",
    textAlign: "left" as const,
  },
  filterItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "8px 20px 8px 44px",
    fontSize: "13px",
    color: "var(--km-text-secondary)",
    cursor: "pointer",
    border: "none",
    backgroundColor: "transparent",
    textAlign: "left" as const,
  },
  filterItemActive: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    width: "100%",
    padding: "8px 20px 8px 44px",
    fontSize: "13px",
    fontWeight: 600,
    color: "var(--km-accent)",
    cursor: "pointer",
    border: "none",
    backgroundColor: "var(--km-accent-soft)",
    textAlign: "left" as const,
  },
  fileList: {
    flex: 1,
    overflowY: "auto",
  },
  fileItem: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
    padding: "14px 20px",
    borderBottom: `1px solid var(--km-border-light)`,
    cursor: "default",
  },
  fileItemSelected: {
    display: "flex",
    alignItems: "flex-start",
    gap: "12px",
    padding: "14px 20px",
    borderBottom: `1px solid var(--km-border-light)`,
    cursor: "default",
    backgroundColor: "var(--km-accent-soft)",
  },
  fileIcon: {
    width: "32px",
    height: "32px",
    borderRadius: "var(--km-radius-sm)",
    backgroundColor: "var(--km-accent-soft)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
    marginTop: "2px",
  },
  fileBody: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    minWidth: 0,
  },
  fileMeta: {
    fontSize: "12px",
    color: "var(--km-text-muted)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },

  /* Center — chat canvas */
  center: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    backgroundColor: "var(--km-bg)",
  },
  chatHeader: {
    padding: "20px 32px 12px",
    flexShrink: 0,
  },
  scopeRow: {
    display: "flex",
    gap: "0",
    margin: "12px 32px",
    flexShrink: 0,
  },
  scopeBtn: {
    flex: 1,
    padding: "7px 0",
    fontSize: "12px",
    fontWeight: 500,
    border: `1px solid #e2e8f0`,
    cursor: "pointer",
    textAlign: "center" as const,
    backgroundColor: "#ffffff",
    color: "#64748b",
    transition: "all 0.15s",
  },
  scopeBtnActive: {
    flex: 1,
    padding: "7px 0",
    fontSize: "12px",
    fontWeight: 600,
    border: `1px solid #1a56db`,
    cursor: "pointer",
    textAlign: "center" as const,
    backgroundColor: "#1a56db",
    color: "#ffffff",
  },
  selectedChips: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "4px",
    padding: "0 32px 10px",
    flexShrink: 0,
  },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: "4px",
    padding: "2px 8px",
    borderRadius: "var(--km-radius-full)",
    fontSize: "11px",
    backgroundColor: "var(--km-accent-soft)",
    color: "var(--km-accent)",
  },
  chipX: {
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    border: "none",
    background: "none",
    padding: 0,
    color: "var(--km-accent)",
  },
  chatMessages: {
    flex: 1,
    overflowY: "auto",
    padding: "16px 32px",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  emptyChat: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "20px",
    padding: "48px 32px",
    textAlign: "center" as const,
  },
  emptySuggestions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "8px",
    justifyContent: "center",
    maxWidth: "440px",
  },
  suggestionBtn: {
    padding: "10px 16px",
    borderRadius: "var(--km-radius-md)",
    border: `1px solid var(--km-border)`,
    backgroundColor: "var(--km-card)",
    fontSize: "13px",
    color: "var(--km-text-secondary)",
    cursor: "pointer",
    textAlign: "left" as const,
    transition: "all 0.15s",
  },
  userMsg: {
    alignSelf: "flex-end",
    backgroundColor: "#e8ebf9",
    color: "#1f2937",
    padding: "12px 16px",
    borderRadius: "12px",
    maxWidth: "75%",
    fontSize: "14px",
    lineHeight: "1.6",
  },
  assistantMsgWrap: {
    alignSelf: "flex-start",
    maxWidth: "85%",
  },
  assistantMsg: {
    backgroundColor: "#ffffff",
    padding: "14px 18px",
    borderRadius: "12px",
    fontSize: "14px",
    lineHeight: "1.75",
    whiteSpace: "pre-wrap" as const,
    wordBreak: "break-word" as const,
    border: "1px solid #e5e7eb",
  },
  disclaimer: {
    fontSize: "11px",
    color: "#9ca3af",
    padding: "8px 18px 0",
    borderTop: "1px solid #f3f4f6",
    marginTop: "10px",
    paddingTop: "8px",
  },
  sources: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: "4px",
    marginTop: "8px",
  },
  chatInputWrap: {
    padding: "0 24px 20px",
    flexShrink: 0,
  },
  chatInputBox: {
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    padding: "10px 12px 10px 16px",
    borderRadius: "20px",
    border: `1px solid #d1d5db`,
    backgroundColor: "#ffffff",
    boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
  },

  /* Empty data panel */
  emptyData: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: "12px",
    padding: "48px 24px",
    textAlign: "center" as const,
    color: "#94a3b8",
  },

  /* Right panel — file list */
  right: {
    width: "280px",
    flexShrink: 0,
    borderLeft: "1px solid #e5e7eb",
    backgroundColor: "#ffffff",
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
  },
  rightHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 20px",
    borderBottom: "1px solid #f1f5f9",
    fontSize: "13px",
    fontWeight: 600,
    color: "#0f172a",
  },
  rightCount: {
    fontSize: "11px",
    fontWeight: 500,
    color: "#94a3b8",
  },
});

/* ── Types ── */
interface FilterDimension {
  id: string; label: string; type: string;
  values: Array<{ value: string; label: string; count: number }>;
}
interface UploadedFile {
  id: string; filename: string; doc_count: number;
  summary: string; keywords: string[];
  filter_values: Record<string, string[]>;
}
interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ doc_id: string; score: number }>;
}

/* ── Prompts ── */
const PROMPTS = [
  "Summarize all documents",
  "What are the key findings?",
  "Extract metrics and numbers",
  "Identify trends and patterns",
  "List all entities mentioned",
  "What risks are identified?",
];

/* ── Component ── */
const Explore: React.FC = () => {
  const styles = useStyles();
  const [searchParams] = useSearchParams();

  // Data
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dataSources, setDataSources] = useState<Array<{ id: string; name: string; source_type: string; status: string; doc_count: number; query_mode: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [schema, setSchema] = useState<{ domain: string; dimensions: FilterDimension[] } | null>(null);
  const [activeFilters, setActiveFilters] = useState<Record<string, Set<string>>>({});
  const [expandedDims, setExpandedDims] = useState<Set<string>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [chatScope, setChatScope] = useState<"all" | "selected">("all");

  // Chat
  const { exploreChatMessages, setExploreChatMessages } = useAppState();
  const messages = exploreChatMessages;
  const setMessages = setExploreChatMessages;
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Chat sessions
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<Array<{ id: string; title: string; message_count: number; updated_at: string }>>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [rightTab, setRightTab] = useState<"docs" | "chats">("docs");

  useEffect(() => {
    loadFiles();
    loadSessions();
    const timer = setTimeout(() => {
      getExtractionInfo().then((r) => setSchema(r.data)).catch(() => {});
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  const loadSessions = () => {
    listChatSessions().then((r) => setSessions(r.data?.sessions || r.data || [])).catch(() => {});
  };

  // Handle query param from home page
  useEffect(() => {
    const q = searchParams.get("q");
    if (q && messages.length === 0) {
      handleChat(q);
    }
  }, [searchParams]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadFiles = async () => {
    setLoading(true);
    try {
      const [filesRes, dsRes] = await Promise.allSettled([
        getUploadedFiles(),
        listDataSources(),
      ]);
      setFiles(filesRes.status === "fulfilled" 
        ? filesRes.value.data.filter((f: any) => f.status === "ready" || !f.status) 
        : []);
      setDataSources(
        dsRes.status === "fulfilled"
          ? dsRes.value.data.filter((s: any) => s.status === "connected")
          : []
      );
    } catch {
      setFiles([]);
      setDataSources([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      setChatScope(next.size > 0 ? "selected" : "all");
      return next;
    });
  };

  const handleChat = async (text?: string) => {
    const q = text || chatInput;
    if (!q.trim() || chatLoading) return;
    const userMsg = { role: "user" as const, content: q };
    setMessages((prev) => [...prev, userMsg]);
    setChatInput("");
    setChatLoading(true);
    try {
      const scope = chatScope === "selected" && selectedIds.size > 0 ? "documents" : "all";
      const docIds = scope === "documents" ? Array.from(selectedIds) : undefined;

      // Build filter dict from active sidebar filters
      const filterDict: Record<string, string> = {};
      for (const [dimId, values] of Object.entries(activeFilters)) {
        if (values.size > 0) {
          filterDict[dimId] = Array.from(values).join(",");
        }
      }
      const filters = Object.keys(filterDict).length > 0 ? filterDict : undefined;

      const res = await askQuestion(q, 5, filters, scope as "all" | "documents", docIds);
      const asstMsg = { role: "assistant" as const, content: res.data.answer, sources: res.data.sources };
      setMessages((prev) => [...prev, asstMsg]);

      // Save to backend (non-blocking)
      const allMsgs = [...messages, userMsg, asstMsg];
      const title = messages.length === 0 ? q.slice(0, 60) : undefined;
      saveChatHistory(sessionId, allMsgs, "default", title)
        .then(() => loadSessions())
        .catch(() => {});
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setChatLoading(false);
    }
  };

  const toggleFilter = (dimId: string, value: string) => {
    setActiveFilters((prev) => {
      const next = { ...prev };
      const set = new Set(next[dimId] || []);
      set.has(value) ? set.delete(value) : set.add(value);
      set.size === 0 ? delete next[dimId] : (next[dimId] = set);
      return next;
    });
  };

  const toggleDim = (id: string) => {
    setExpandedDims((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };

  // Filter files
  const filtered = files.filter((f) => {
    if (search) {
      const s = search.toLowerCase();
      if (!f.filename.toLowerCase().includes(s) && !f.summary.toLowerCase().includes(s) &&
          !f.keywords.some((k) => k.toLowerCase().includes(s))) return false;
    }
    for (const [dimId, vals] of Object.entries(activeFilters)) {
      if (vals.size === 0) continue;
      if (dimId === "_keywords") {
        if (!f.keywords.some((kw) => vals.has(kw))) return false;
      } else if (dimId === "_doc_type") {
        const ext = f.filename.split(".").pop()?.toLowerCase() || "unknown";
        if (!vals.has(ext)) return false;
      } else if (dimId === "_document") {
        if (!vals.has(f.id)) return false;
      } else {
        if (!(f.filter_values[dimId] || []).some((v) => vals.has(v))) return false;
      }
    }
    return true;
  });

  // Collect keywords across all files
  const kwCounts: Record<string, number> = {};
  for (const f of files) for (const kw of f.keywords) kwCounts[kw] = (kwCounts[kw] || 0) + 1;

  // Deterministic: file type counts
  const fileTypeCounts: Record<string, number> = {};
  for (const f of files) {
    const ext = f.filename.split(".").pop()?.toLowerCase() || "other";
    fileTypeCounts[ext] = (fileTypeCounts[ext] || 0) + f.doc_count;
  }

  // Deterministic: source file counts
  const sourceFileCounts: Record<string, { id: string; count: number }> = {};
  for (const f of files) {
    sourceFileCounts[f.filename] = { id: f.id, count: f.doc_count };
  }

  return (
    <div className={styles.page}>
      {/* ── Left: Data Layer ── */}
      <div className={styles.left}>
        <div className={styles.leftHeader}>
          <Filter20Regular /> Filters
        </div>

        {/* ── Deterministic Filters (always accurate) ── */}

        {/* File Type */}
        {Object.keys(fileTypeCounts).length > 0 && (() => {
          const expanded = expandedDims.has("_doc_type");
          const active = activeFilters["_doc_type"];
          return (
            <div className={styles.filterGroup}>
              <button className={styles.filterGroupBtn} onClick={() => toggleDim("_doc_type")}>
                <ChevronRight20Regular style={{ fontSize: 16, flexShrink: 0, transform: expanded ? "rotate(90deg)" : "none", transition: "transform 0.15s" }} />
                File Type
              </button>
              {expanded && Object.entries(fileTypeCounts).sort((a, b) => b[1] - a[1]).map(([ext, count]) => (
                <button key={ext} className={active?.has(ext) ? styles.filterItemActive : styles.filterItem}
                  onClick={() => toggleFilter("_doc_type", ext)}>
                  <span style={{ flex: 1 }}>.{ext}</span>
                  <Caption1>{count}</Caption1>
                </button>
              ))}
            </div>
          );
        })()}

        {/* Source */}
        {Object.keys(sourceFileCounts).length > 1 && (() => {
          const expanded = expandedDims.has("_document");
          const active = activeFilters["_document"];
          return (
            <div className={styles.filterGroup}>
              <button className={styles.filterGroupBtn} onClick={() => toggleDim("_document")}>
                <ChevronRight20Regular style={{ fontSize: 16, flexShrink: 0, transform: expanded ? "rotate(90deg)" : "none", transition: "transform 0.15s" }} />
                Source
              </button>
              {expanded && Object.entries(sourceFileCounts).map(([name, info]) => (
                <button key={info.id} className={active?.has(info.id) ? styles.filterItemActive : styles.filterItem}
                  onClick={() => toggleFilter("_document", info.id)}>
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
                  <Caption1>{info.count}</Caption1>
                </button>
              ))}
            </div>
          );
        })()}

        {/* ── AI-Generated Filters (with badge) ── */}
        {schema?.dimensions && schema.dimensions.length > 0 && (
          <div style={{ padding: "8px 16px 4px", fontSize: 10, fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.8px", display: "flex", alignItems: "center", gap: 6 }}>
            AI-detected
            <span style={{ fontSize: 9, padding: "1px 6px", borderRadius: 4, background: "#f0f9ff", color: "#2563eb", fontWeight: 500, textTransform: "none", letterSpacing: 0 }}>auto</span>
          </div>
        )}

        {/* AI Filters */}
        {schema?.dimensions.map((dim) => {
          const expanded = expandedDims.has(dim.id);
          const active = activeFilters[dim.id];
          return (
            <div key={dim.id} className={styles.filterGroup}>
              <button className={styles.filterGroupBtn} onClick={() => toggleDim(dim.id)}>
                <ChevronRight20Regular style={{
                  fontSize: 16, flexShrink: 0,
                  transform: expanded ? "rotate(90deg)" : "none",
                  transition: "transform 0.15s",
                }} />
                {dim.label}
              </button>
              {expanded && dim.values.map((v) => (
                <button
                  key={v.value}
                  className={active?.has(v.value) ? styles.filterItemActive : styles.filterItem}
                  onClick={() => toggleFilter(dim.id, v.value)}
                >
                  <span style={{ flex: 1 }}>{v.label}</span>
                  <Caption1>{v.count}</Caption1>
                </button>
              ))}
            </div>
          );
        })}

        {/* Keywords */}
        {Object.keys(kwCounts).length > 0 && (() => {
          const exp = expandedDims.has("_keywords");
          const active = activeFilters["_keywords"];
          return (
            <div className={styles.filterGroup}>
              <button className={styles.filterGroupBtn} onClick={() => toggleDim("_keywords")}>
                <ChevronRight20Regular style={{ fontSize: 16, flexShrink: 0, transform: exp ? "rotate(90deg)" : "none", transition: "transform 0.15s" }} />
                Key Phrases
              </button>
              {exp && Object.entries(kwCounts).sort((a, b) => b[1] - a[1]).slice(0, 15).map(([kw, c]) => (
                <button key={kw} className={active?.has(kw) ? styles.filterItemActive : styles.filterItem} onClick={() => toggleFilter("_keywords", kw)}>
                  <span style={{ flex: 1 }}>{kw}</span>
                  <Caption1>{c}</Caption1>
                </button>
              ))}
            </div>
          );
        })()}
      </div>

      {/* ── Center: Chat Canvas ── */}
      <div className={styles.center}>
        {/* Scope */}
        <div className={styles.scopeRow}>
          <button
            className={chatScope === "all" ? styles.scopeBtnActive : styles.scopeBtn}
            style={{ borderRadius: "var(--km-radius-sm) 0 0 var(--km-radius-sm)" }}
            onClick={() => setChatScope("all")}
          >
            All Documents
          </button>
          <button
            className={chatScope === "selected" ? styles.scopeBtnActive : styles.scopeBtn}
            style={{ borderRadius: "0 var(--km-radius-sm) var(--km-radius-sm) 0" }}
            onClick={() => selectedIds.size > 0 && setChatScope("selected")}
          >
            Selected ({selectedIds.size})
          </button>
        </div>

        {chatScope === "selected" && selectedIds.size > 0 && (
          <div className={styles.selectedChips}>
            {Array.from(selectedIds).map((id) => {
              const f = files.find((x) => x.id === id);
              return (
                <span key={id} className={styles.chip}>
                  {f?.filename || id}
                  <button className={styles.chipX} onClick={() => toggleSelect(id)}>
                    <Dismiss12Regular />
                  </button>
                </span>
              );
            })}
          </div>
        )}

        {/* Active filter chips */}
        {Object.keys(activeFilters).length > 0 && (
          <div className={styles.selectedChips}>
            {Object.entries(activeFilters).map(([dimId, values]) =>
              Array.from(values).map((v) => (
                <span key={`${dimId}-${v}`} className={styles.chip}>
                  {v}
                  <button className={styles.chipX} onClick={() => toggleFilter(dimId, v)}>
                    <Dismiss12Regular />
                  </button>
                </span>
              ))
            )}
          </div>
        )}

        {/* Messages */}
        <div className={styles.chatMessages}>
          {messages.length === 0 ? (
            <div className={styles.emptyChat}>
              <Sparkle20Regular style={{ fontSize: 40, color: "var(--km-text-muted)" }} />
              <Text size={500} weight="semibold" style={{ color: "var(--km-text-primary)" }}>
                Ask anything about your data
              </Text>
              <Text size={300} style={{ color: "var(--km-text-muted)" }}>
                Chat with your documents, extract insights, or ask follow-up questions.
              </Text>
              <div className={styles.emptySuggestions}>
                {PROMPTS.map((p) => (
                  <button key={p} className={styles.suggestionBtn} onClick={() => handleChat(p)}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) => (
                msg.role === "user" ? (
                  <div key={i} className={styles.userMsg}>
                    <ChatContent content={msg.content} />
                  </div>
                ) : (
                  <div key={i} className={styles.assistantMsgWrap}>
                    <div className={styles.assistantMsg}>
                      <ChatContent content={msg.content} />
                      {msg.sources && msg.sources.length > 0 && (
                        <div className={styles.sources}>
                          {msg.sources.map((s, j) => (
                            <Badge key={j} appearance="outline" size="small" shape="rounded">{s.doc_id}</Badge>
                          ))}
                        </div>
                      )}
                      <div className={styles.disclaimer}>AI-generated content may be incorrect</div>
                    </div>
                  </div>
                )
              ))}
              {chatLoading && (
                <div className={styles.assistantMsgWrap}>
                  <div className={styles.assistantMsg}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#9ca3af", fontSize: 14 }}>
                      <span style={{ animation: "pulse 1.5s ease-in-out infinite" }}>●</span>
                      <span style={{ animation: "pulse 1.5s ease-in-out 0.3s infinite" }}>●</span>
                      <span style={{ animation: "pulse 1.5s ease-in-out 0.6s infinite" }}>●</span>
                      <style>{`@keyframes pulse { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }`}</style>
                    </div>
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
            </>
          )}
        </div>

        {/* Input */}
        <div className={styles.chatInputWrap}>
          <div className={styles.chatInputBox}>
            <button
              onClick={() => { setSessionId(crypto.randomUUID()); setMessages([]); }}
              title="New conversation"
              style={{
                border: "none", background: "none", cursor: "pointer", padding: 4,
                display: "flex", alignItems: "flex-start", flexShrink: 0,
                color: "#6366f1", borderRadius: 8, marginTop: 2,
              }}
            >
              <Add20Regular />
            </button>
            <textarea
              placeholder="Ask a question..."
              value={chatInput}
              rows={1}
              onChange={(e) => {
                setChatInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleChat();
                }
              }}
              style={{
                flex: 1, border: "none", outline: "none", fontSize: 14,
                background: "transparent", color: "#1f2937", fontFamily: "inherit",
                resize: "none", overflow: "auto", lineHeight: "1.5",
                maxHeight: 150, minHeight: 24,
              }}
            />
            <button
              onClick={() => handleChat()}
              disabled={chatLoading || !chatInput.trim()}
              title="Send"
              style={{
                border: "none", background: "none", cursor: chatInput.trim() ? "pointer" : "default",
                padding: 4, display: "flex", alignItems: "flex-start", flexShrink: 0,
                color: chatInput.trim() ? "#6366f1" : "#d1d5db", marginTop: 2,
              }}
            >
              <Send24Regular />
            </button>
          </div>
        </div>
      </div>

      {/* ── Right Panel: Documents / Chats ── */}
      <div className={styles.right}>
        {/* Tab switcher */}
        <div style={{ display: "flex", borderBottom: "1px solid #e5e7eb" }}>
          <button onClick={() => setRightTab("docs")} style={{
            flex: 1, padding: "12px 0", border: "none", cursor: "pointer", fontFamily: "inherit",
            fontSize: 13, fontWeight: 600, background: "none",
            color: rightTab === "docs" ? "#2563eb" : "#94a3b8",
            borderBottom: rightTab === "docs" ? "2px solid #2563eb" : "2px solid transparent",
          }}>Documents</button>
          <button onClick={() => setRightTab("chats")} style={{
            flex: 1, padding: "12px 0", border: "none", cursor: "pointer", fontFamily: "inherit",
            fontSize: 13, fontWeight: 600, background: "none",
            color: rightTab === "chats" ? "#2563eb" : "#94a3b8",
            borderBottom: rightTab === "chats" ? "2px solid #2563eb" : "2px solid transparent",
          }}>Chats{sessions.filter((s) => s.message_count > 0).length > 0 ? ` (${sessions.filter((s) => s.message_count > 0).length})` : ""}</button>
        </div>

        {/* Documents tab */}
        {rightTab === "docs" && (
          <>
        <div className={styles.searchWrap}>
          <Input
            contentBefore={<Search24Regular />}
            placeholder="Search files..."
            value={search}
            onChange={(_, d) => setSearch(d.value)}
            size="small"
            style={{ width: "100%" }}
          />
        </div>

        {/* Document type filter chips */}
        {(() => {
          const typeCounts: Record<string, number> = {};
          for (const f of files) {
            const ext = f.filename.split(".").pop()?.toLowerCase() || "unknown";
            typeCounts[ext] = (typeCounts[ext] || 0) + 1;
          }
          if (Object.keys(typeCounts).length <= 1) return null;
          const active = activeFilters["_doc_type"];
          return (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, padding: "8px 16px" }}>
              {Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).map(([ext, count]) => (
                <button
                  key={ext}
                  onClick={() => toggleFilter("_doc_type", ext)}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 6,
                    border: active?.has(ext) ? "1px solid #1a56db" : "1px solid #e2e8f0",
                    background: active?.has(ext) ? "#dbeafe" : "#fff",
                    color: active?.has(ext) ? "#1a56db" : "#64748b",
                    fontSize: 11,
                    fontWeight: 600,
                    cursor: "pointer",
                    fontFamily: "inherit",
                  }}
                >
                  .{ext} ({count})
                </button>
              ))}
            </div>
          );
        })()}

        <div className={styles.fileList}>
          {loading ? (
            <div className={styles.emptyData}><Spinner size="small" /></div>
          ) : filtered.length === 0 ? (
            <div className={styles.emptyData}>
              <DocumentText24Regular style={{ fontSize: 32 }} />
              <Text size={200}>No documents found</Text>
            </div>
          ) : (
            filtered.map((f) => (
              <div key={f.id} className={selectedIds.has(f.id) ? styles.fileItemSelected : styles.fileItem}>
                <div onClick={() => toggleSelect(f.id)} style={{ paddingTop: 2 }}>
                  <Checkbox checked={selectedIds.has(f.id)} size="medium" />
                </div>
                <div className={styles.fileBody}>
                  <Text weight="semibold" size={200}>{f.filename}</Text>
                  <div className={styles.fileMeta}>
                    {f.doc_count} records
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Connected data sources */}
        {dataSources.length > 0 && (
          <>
            <div className={styles.leftHeader} style={{ borderTop: "1px solid var(--km-border)" }}>
              <Database20Regular /> Live Sources
            </div>
            <div style={{ padding: "4px 0" }}>
              {dataSources.map((ds) => (
                <div key={ds.id} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  padding: "8px 16px", fontSize: 12,
                }}>
                  <PlugConnected20Regular style={{ color: "#059669", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <Text weight="semibold" size={200} style={{ display: "block" }}>{ds.name}</Text>
                    <span style={{ color: "#94a3b8", fontSize: 11 }}>
                      {ds.doc_count.toLocaleString()} rows · {ds.query_mode}
                    </span>
                  </div>
                  <Badge appearance="filled" color="success" size="small">live</Badge>
                </div>
              ))}
            </div>
          </>
        )}
          </>
        )}

        {/* Chats tab */}
        {rightTab === "chats" && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div style={{ flex: 1, overflowY: "auto" }}>
              {sessions.filter((s) => s.message_count > 0).length === 0 ? (
                <div style={{ padding: "40px 20px", textAlign: "center", color: "#94a3b8" }}>
                  <Chat20Regular style={{ fontSize: 32, marginBottom: 8 }} />
                  <Text block size={200}>No conversations yet</Text>
                  <Text block size={200} style={{ marginTop: 4 }}>Start chatting to save your conversations</Text>
                </div>
              ) : (
                sessions.filter((s) => s.message_count > 0).map((sess) => (
                  <div key={sess.id}
                    onClick={async () => {
                      try {
                        const res = await loadChatHistory(sess.id);
                        setSessionId(sess.id);
                        setMessages(res.data.messages || []);
                        setRightTab("docs");
                      } catch { /* ignore */ }
                    }}
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      padding: "10px 16px", cursor: "pointer",
                      borderBottom: "1px solid #f1f5f9",
                      backgroundColor: sess.id === sessionId ? "#eff6ff" : "transparent",
                      transition: "background 0.12s",
                    }}
                  >
                    <Chat20Regular style={{ color: sess.id === sessionId ? "#2563eb" : "#94a3b8", flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: "#334155", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {sess.title || "Untitled"}
                      </div>
                    </div>
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        try {
                          await deleteChatSession(sess.id);
                          setSessions((prev) => prev.filter((s) => s.id !== sess.id));
                          if (sess.id === sessionId) {
                            setSessionId(crypto.randomUUID());
                            setMessages([]);
                          }
                        } catch { /* ignore */ }
                      }}
                      style={{ border: "none", background: "none", cursor: "pointer", color: "#ef4444", padding: 2, flexShrink: 0, opacity: 0.6, transition: "opacity 0.12s" }}
                      title="Delete conversation"
                    >
                      <Delete20Regular />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ── Chat Content with Chart Rendering ── */
const ChatContent: React.FC<{ content: string }> = ({ content }) => {
  // Check for ```chart ... ``` blocks
  const chartRegex = /```chart\s*\n([\s\S]*?)\n```/g;
  const parts: Array<{ type: "text" | "chart"; value: string }> = [];
  let lastIndex = 0;
  let match;

  while ((match = chartRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: content.slice(lastIndex, match.index) });
    }
    parts.push({ type: "chart", value: match[1] });
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < content.length) {
    parts.push({ type: "text", value: content.slice(lastIndex) });
  }

  // If no chart blocks, render as formatted text
  if (parts.length === 0 || (parts.length === 1 && parts[0].type === "text")) {
    return <>{renderMarkdown(content)}</>;
  }

  return (
    <>
      {parts.map((part, i) => {
        if (part.type === "text") {
          return <span key={i}>{renderMarkdown(part.value)}</span>;
        }
        // Parse chart JSON
        try {
          const chart = JSON.parse(part.value);
          const data = chart.data || [];
          if (data.length === 0) return null;

          return (
            <div key={i} style={{
              margin: "12px 0", padding: "16px",
              borderRadius: 12, backgroundColor: "#f9fafb",
              border: "1px solid #f1f5f9",
            }}>
              {chart.title && (
                <div style={{ fontSize: 13, fontWeight: 600, color: "#0f172a", marginBottom: 10 }}>
                  {chart.title}
                </div>
              )}
              {chart.type === "donut" && <DonutChart data={data} height={200} />}
              {chart.type === "bar" && <BarChart data={data} height={200} />}
              {chart.type === "line" && <BarChart data={data} height={200} />}
              {!["donut", "bar", "line"].includes(chart.type) && <BarChart data={data} height={200} />}
            </div>
          );
        } catch {
          return <span key={i}>{part.value}</span>;
        }
      })}
    </>
  );
};

export default Explore;
