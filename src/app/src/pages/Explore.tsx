import React, { useState, useEffect, useRef } from "react";
import { makeStyles, Text, Badge, Spinner, Caption1 } from "@fluentui/react-components";
import {
  Send24Regular, Sparkle20Regular, Add20Regular, Chat20Regular,
  Database20Regular, DocumentText20Regular, Delete20Regular,
  ChevronDown20Regular, ChevronRight20Regular, Dismiss12Regular,
  Filter20Regular,
} from "@fluentui/react-icons";
import { askQuestion, getUploadedFiles, listDataSources, saveChatHistory, listChatSessions, loadChatHistory, deleteChatSession } from "../api/client";
import { useAppState } from "../context/AppStateContext";
import { useSearchParams, useLocation } from "react-router-dom";
import { DonutChart, BarChart } from "../components/Charts";
import { renderMarkdown } from "../utils/markdown";

/* ═══════════════════════════════════════════
   Styles
   ═══════════════════════════════════════════ */
const useStyles = makeStyles({
  page: { display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", backgroundColor: "#f9fafb" },

  /* ── Context bar (top) ── */
  contextBar: {
    display: "flex", alignItems: "center", gap: "12px", padding: "8px 24px",
    backgroundColor: "#ffffff", borderBottom: "1px solid #e5e7eb", flexShrink: 0,
    fontSize: "12px", color: "#64748b", flexWrap: "wrap" as const,
  },
  contextItem: { display: "flex", alignItems: "center", gap: "4px" },
  contextValue: { fontWeight: 600, color: "#0f172a" },
  filterChip: {
    display: "inline-flex", alignItems: "center", gap: "3px",
    padding: "2px 8px", borderRadius: "10px", fontSize: "11px",
    backgroundColor: "#eff6ff", color: "#2563eb", fontWeight: 500,
  },
  filterX: {
    cursor: "pointer", border: "none", background: "none",
    padding: 0, color: "#2563eb", display: "flex", alignItems: "center", fontSize: "10px",
  },
  contextSep: { width: "1px", height: "16px", backgroundColor: "#e2e8f0" },
  historyBtn: {
    marginLeft: "auto", border: "none", background: "none", cursor: "pointer",
    fontSize: "12px", color: "#64748b", display: "flex", alignItems: "center", gap: "4px",
    fontFamily: "inherit", fontWeight: 500,
  },

  /* ── Chat area ── */
  chatArea: { flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", maxWidth: "840px", width: "100%", margin: "0 auto" },
  chatMessages: { flex: 1, overflowY: "auto", padding: "24px 32px", display: "flex", flexDirection: "column", gap: "16px" },

  /* Empty */
  emptyChat: {
    flex: 1, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center", gap: "16px",
    padding: "48px 32px", textAlign: "center" as const,
  },
  suggestions: { display: "flex", flexWrap: "wrap" as const, gap: "8px", justifyContent: "center", maxWidth: "520px" },
  suggestionBtn: {
    padding: "10px 16px", borderRadius: "12px", border: "1px solid #e2e8f0",
    backgroundColor: "#ffffff", fontSize: "13px", color: "#475569",
    cursor: "pointer", fontFamily: "inherit", transition: "all 0.12s", textAlign: "left" as const,
  },

  /* Messages */
  userMsg: {
    alignSelf: "flex-end", backgroundColor: "#e8ebf9", color: "#1f2937",
    padding: "12px 16px", borderRadius: "16px 16px 4px 16px",
    maxWidth: "75%", fontSize: "14px", lineHeight: "1.6",
  },
  assistantWrap: { alignSelf: "flex-start", maxWidth: "90%", display: "flex", flexDirection: "column", gap: "4px" },
  assistantMsg: {
    backgroundColor: "#ffffff", padding: "16px 20px", borderRadius: "4px 16px 16px 16px",
    fontSize: "14px", lineHeight: "1.75", whiteSpace: "pre-wrap" as const,
    wordBreak: "break-word" as const, border: "1px solid #e5e7eb",
  },

  /* Evidence toggle (under each answer) */
  evidenceToggle: {
    display: "flex", alignItems: "center", gap: "4px",
    border: "none", background: "none", cursor: "pointer",
    fontSize: "11px", color: "#94a3b8", fontFamily: "inherit",
    padding: "4px 0", fontWeight: 500,
  },
  evidenceList: {
    padding: "8px 0 4px", display: "flex", flexDirection: "column", gap: "6px",
  },
  evidenceItem: {
    padding: "8px 12px", borderRadius: "8px", backgroundColor: "#f8fafc",
    border: "1px solid #f1f5f9", fontSize: "12px",
  },
  evidenceDoc: { fontWeight: 600, color: "#0f172a" },
  evidenceText: { color: "#64748b", marginTop: "2px", lineHeight: "1.4" },
  evidenceScore: { color: "#2563eb", fontWeight: 600, fontSize: "11px" },

  disclaimer: { fontSize: "11px", color: "#9ca3af", marginTop: "4px" },

  /* Input */
  inputWrap: { padding: "0 32px 20px", flexShrink: 0, maxWidth: "840px", width: "100%", margin: "0 auto" },
  inputBox: {
    display: "flex", alignItems: "flex-start", gap: "8px",
    padding: "12px 14px 12px 18px", borderRadius: "20px",
    border: "1px solid #d1d5db", backgroundColor: "#ffffff",
    boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
  },

  /* History drawer */
  historyDrawer: {
    position: "fixed" as const, top: 0, right: 0, bottom: 0,
    width: "300px", backgroundColor: "#ffffff", borderLeft: "1px solid #e5e7eb",
    boxShadow: "-4px 0 16px rgba(0,0,0,0.06)", zIndex: 20,
    display: "flex", flexDirection: "column", overflow: "hidden",
  },
  historyHeader: {
    display: "flex", alignItems: "center", justifyContent: "space-between",
    padding: "16px 20px", borderBottom: "1px solid #e5e7eb",
    fontSize: "14px", fontWeight: 600, color: "#0f172a",
  },
  historyItem: {
    display: "flex", alignItems: "center", gap: "10px",
    padding: "12px 20px", borderBottom: "1px solid #f8fafc",
    cursor: "pointer", fontSize: "13px",
  },
  historyTitle: { flex: 1, fontWeight: 500, color: "#1e293b", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const },
  historyMeta: { color: "#94a3b8", fontSize: "11px" },
  overlay: {
    position: "fixed" as const, top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: "rgba(0,0,0,0.15)", zIndex: 19,
  },
});

/* ═══════════════════════════════════════════
   Chat content renderer
   ═══════════════════════════════════════════ */
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
          } catch { /* render as text */ }
        }
        return <div key={i} dangerouslySetInnerHTML={{ __html: renderMarkdown(part) as string }} />;
      })}
    </>
  );
};

const PROMPTS = [
  "Summarize all documents",
  "What are the key findings?",
  "Identify trends and patterns",
  "What are the main topics?",
  "What risks or issues exist?",
  "Show me the top metrics",
];

/* ═══════════════════════════════════════════
   Component
   ═══════════════════════════════════════════ */
const Explore: React.FC = () => {
  const styles = useStyles();
  const [searchParams] = useSearchParams();
  const location = useLocation();

  // Data
  const [files, setFiles] = useState<any[]>([]);
  const [dataSources, setDataSources] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Chat
  const { exploreChatMessages, setExploreChatMessages } = useAppState();
  const messages = exploreChatMessages;
  const setMessages = setExploreChatMessages;
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [expandedSources, setExpandedSources] = useState<Set<number>>(new Set());

  // Sessions
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());
  const [sessions, setSessions] = useState<any[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Load
  useEffect(() => { loadData(); loadSessions(); }, [location.key]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [fR, dR] = await Promise.allSettled([getUploadedFiles(), listDataSources()]);
      setFiles(fR.status === "fulfilled" ? fR.value.data.filter((f: any) => f.status === "ready" || !f.status) : []);
      setDataSources(dR.status === "fulfilled" ? dR.value.data.filter((s: any) => s.status === "connected") : []);
    } catch {} finally { setLoading(false); }
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
      const res = await askQuestion(q, 5);
      const asstMsg = { role: "assistant" as const, content: res.data.answer, sources: res.data.sources };
      setMessages(prev => [...prev, asstMsg]);
      const allMsgs = [...messages, userMsg, asstMsg];
      const title = messages.length === 0 ? q.slice(0, 60) : undefined;
      saveChatHistory(sessionId, allMsgs, "default", title).then(() => loadSessions()).catch(() => {});
    } catch (err: unknown) {
      setMessages(prev => [...prev, { role: "assistant", content: `Error: ${err instanceof Error ? err.message : "Unknown"}` }]);
    } finally { setChatLoading(false); }
  };

  const startNew = () => { setSessionId(crypto.randomUUID()); setMessages([]); setExpandedSources(new Set()); };

  const loadSession = async (sid: string) => {
    try {
      const r = await loadChatHistory(sid);
      const msgs = r.data?.messages || r.data || [];
      setSessionId(sid);
      setMessages(msgs.map((m: any) => ({ role: m.role, content: m.content, sources: m.sources })));
      setShowHistory(false);
    } catch {}
  };

  const deleteSessionHandler = async (sid: string) => {
    try { await deleteChatSession(sid); loadSessions(); } catch {}
  };

  const toggleSource = (idx: number) => {
    setExpandedSources(prev => { const n = new Set(prev); n.has(idx) ? n.delete(idx) : n.add(idx); return n; });
  };

  // Computed
  const totalRecords = files.reduce((s, f) => s + (f.doc_count || 0), 0) + dataSources.reduce((s, d) => s + (d.doc_count || 0), 0);
  const sessionCount = sessions.filter(s => s.message_count > 0).length;

  return (
    <div className={styles.page}>
      {/* ═══ CONTEXT BAR ═══ */}
      <div className={styles.contextBar}>
        <div className={styles.contextItem}>
          <DocumentText20Regular style={{ color: "#2563eb" }} />
          <span className={styles.contextValue}>{totalRecords.toLocaleString()}</span> records
        </div>
        <div className={styles.contextSep} />
        <div className={styles.contextItem}>
          {files.length} file{files.length !== 1 ? "s" : ""}
          {dataSources.length > 0 && <span style={{ marginLeft: 4 }}>· {dataSources.length} source{dataSources.length !== 1 ? "s" : ""}</span>}
        </div>

        <button className={styles.historyBtn} onClick={() => setShowHistory(true)}>
          <Chat20Regular style={{ fontSize: 16 }} />
          History{sessionCount > 0 ? ` (${sessionCount})` : ""}
        </button>
      </div>

      {/* ═══ CHAT ═══ */}
      <div className={styles.chatArea}>
        <div className={styles.chatMessages}>
          {messages.length === 0 ? (
            <div className={styles.emptyChat}>
              <Sparkle20Regular style={{ fontSize: 40, color: "#cbd5e1" }} />
              <Text size={500} weight="semibold" style={{ color: "#0f172a" }}>
                Ask anything about your data
              </Text>
              <Text size={300} style={{ color: "#64748b" }}>
                Charts, summaries, trends, and analysis — all through conversation.
              </Text>
              <div className={styles.suggestions}>
                {PROMPTS.map(p => (
                  <button key={p} className={styles.suggestionBtn} onClick={() => handleChat(p)}>{p}</button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, i) =>
                msg.role === "user" ? (
                  <div key={i} className={styles.userMsg}><ChatContent content={msg.content} /></div>
                ) : (
                  <div key={i} className={styles.assistantWrap}>
                    <div className={styles.assistantMsg}>
                      <ChatContent content={msg.content} />
                    </div>

                    {/* Evidence toggle */}
                    {(msg.sources?.length ?? 0) > 0 && (
                      <>
                        <button className={styles.evidenceToggle} onClick={() => toggleSource(i)}>
                          {expandedSources.has(i) ? <ChevronDown20Regular /> : <ChevronRight20Regular />}
                          {(msg.sources || []).length} source{(msg.sources || []).length !== 1 ? "s" : ""} used
                        </button>
                        {expandedSources.has(i) && (
                          <div className={styles.evidenceList}>
                            {(msg.sources || []).map((src: any, j: number) => (
                              <div key={j} className={styles.evidenceItem}>
                                <div style={{ display: "flex", justifyContent: "space-between" }}>
                                  <span className={styles.evidenceDoc}>{src.doc_id}</span>
                                  <span className={styles.evidenceScore}>{(src.score * 100).toFixed(0)}% match</span>
                                </div>
                                {src.text && <div className={styles.evidenceText}>{src.text.slice(0, 200)}...</div>}
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                    <div className={styles.disclaimer}>AI-generated content may be incorrect</div>
                  </div>
                )
              )}
              {chatLoading && (
                <div className={styles.assistantWrap}>
                  <div className={styles.assistantMsg}>
                    <span style={{ color: "#9ca3af", fontSize: 14 }}>
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

        {/* Input */}
        <div className={styles.inputWrap}>
          <div className={styles.inputBox}>
            <button onClick={startNew} title="New conversation"
              style={{ border: "none", background: "none", cursor: "pointer", padding: 4,
                display: "flex", color: "#6366f1", marginTop: 2, flexShrink: 0 }}>
              <Add20Regular />
            </button>
            <textarea
              placeholder="Ask a question..."
              value={chatInput} rows={1}
              onChange={e => { setChatInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px"; }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChat(); } }}
              style={{ flex: 1, border: "none", outline: "none", fontSize: 14, background: "transparent",
                color: "#1f2937", fontFamily: "inherit", resize: "none", overflow: "auto",
                lineHeight: "1.5", maxHeight: 150, minHeight: 24 }}
            />
            <button onClick={() => handleChat()} disabled={chatLoading || !chatInput.trim()} title="Send"
              style={{ border: "none", background: "none", cursor: chatInput.trim() ? "pointer" : "default",
                padding: 4, display: "flex", color: chatInput.trim() ? "#6366f1" : "#d1d5db", marginTop: 2, flexShrink: 0 }}>
              <Send24Regular />
            </button>
          </div>
        </div>
      </div>

      {/* ═══ HISTORY DRAWER ═══ */}
      {showHistory && (
        <>
          <div className={styles.overlay} onClick={() => setShowHistory(false)} />
          <div className={styles.historyDrawer}>
            <div className={styles.historyHeader}>
              Chat History
              <button onClick={() => setShowHistory(false)} style={{ border: "none", background: "none", cursor: "pointer", color: "#94a3b8" }}>
                <Dismiss12Regular />
              </button>
            </div>
            <div style={{ overflowY: "auto", flex: 1 }}>
              <div className={styles.historyItem} onClick={() => { startNew(); setShowHistory(false); }}
                style={{ color: "#2563eb", fontWeight: 600 }}>
                <Add20Regular /> New conversation
              </div>
              {sessions.filter(s => s.message_count > 0).map(sess => (
                <div key={sess.id} className={styles.historyItem} onClick={() => loadSession(sess.id)}>
                  <Chat20Regular style={{ color: "#94a3b8", flexShrink: 0 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className={styles.historyTitle}>{sess.title || "Untitled"}</div>
                    <div className={styles.historyMeta}>{sess.message_count} messages</div>
                  </div>
                  <button onClick={e => { e.stopPropagation(); deleteSessionHandler(sess.id); }}
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
