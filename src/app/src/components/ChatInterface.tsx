import React, { useState, useRef, useEffect } from "react";
import {
  makeStyles,
  tokens,
  Input,
  Button,
  Body1,
  Subtitle2,
  Caption1,
} from "@fluentui/react-components";
import { Send24Regular, ChatBubblesQuestion24Regular, Dismiss20Regular } from "@fluentui/react-icons";
import { askQuestion, fetchCitationContent } from "../api/client";
import { renderMarkdown } from "../utils/markdown";

const useStyles = makeStyles({
  container: {
    display: "flex",
    flexDirection: "column",
    flex: 1,
    overflow: "hidden",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    padding: "16px",
  },
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: "12px",
    padding: "24px 16px",
    textAlign: "center" as const,
  },
  emptyIcon: {
    width: "48px",
    height: "48px",
    borderRadius: "50%",
    backgroundColor: tokens.colorNeutralBackground3,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  chips: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    width: "100%",
    maxWidth: "260px",
    marginTop: "8px",
  },
  chip: {
    padding: "8px 12px",
    borderRadius: "8px",
    backgroundColor: "#f1f5f9",
    fontSize: "12px",
    color: "#475569",
    cursor: "pointer",
    textAlign: "left" as const,
    border: "none",
    transition: "background-color 0.1s",
  },
  userMsg: {
    alignSelf: "flex-end",
    backgroundColor: "#e8ebf9",
    color: "#1f2937",
    padding: "10px 14px",
    borderRadius: "12px",
    maxWidth: "82%",
    fontSize: tokens.fontSizeBase300,
    lineHeight: tokens.lineHeightBase300,
  },
  assistantMsgWrap: {
    alignSelf: "flex-start",
    maxWidth: "90%",
  },
  assistantMsg: {
    backgroundColor: "#ffffff",
    padding: "10px 14px",
    borderRadius: "12px",
    fontSize: tokens.fontSizeBase300,
    lineHeight: tokens.lineHeightBase400,
    wordBreak: "break-word" as const,
    border: "1px solid #e5e7eb",
  },
  msgDisclaimer: {
    fontSize: "10px",
    color: "#9ca3af",
    borderTop: "1px solid #f3f4f6",
    marginTop: "8px",
    paddingTop: "6px",
  },
  inputRow: {
    display: "flex",
    gap: "6px",
    padding: "12px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1,
    alignItems: "center",
  },
  sources: { marginTop: "8px", display: "flex", flexWrap: "wrap" as const, alignItems: "center", gap: "8px" },
  sourceLink: {
    border: `1px solid ${tokens.colorNeutralStroke2}`,
    background: tokens.colorNeutralBackground2,
    padding: "2px 8px",
    borderRadius: "4px",
    cursor: "pointer",
    fontWeight: 500,
    color: "#2563eb",
    textAlign: "left" as const,
    textDecoration: "none",
    fontSize: "12px",
    wordBreak: "break-all" as const,
  },
  overlay: {
    position: "fixed" as const,
    inset: 0,
    backgroundColor: "rgba(15,23,42,0.35)",
    zIndex: 1000,
  },
  drawer: {
    position: "fixed" as const,
    top: 0,
    right: 0,
    bottom: 0,
    width: "440px",
    maxWidth: "90vw",
    backgroundColor: "#ffffff",
    boxShadow: "-4px 0 16px rgba(0,0,0,0.12)",
    zIndex: 1001,
    display: "flex",
    flexDirection: "column",
  },
  drawerHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 16px",
    borderBottom: "1px solid #e5e7eb",
    fontWeight: 600,
    fontSize: "14px",
    color: "#0f172a",
  },
  drawerBody: { overflowY: "auto" as const, flex: 1, padding: "16px" },
});

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: any[];
}

const ChatInterface: React.FC = () => {
  const styles = useStyles();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [conversationId] = useState<string>(() => crypto.randomUUID());
  const [activeCitation, setActiveCitation] = useState<{ title: string; content: string } | null>(null);
  const [citationLoading, setCitationLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const openCitation = async (src: any) => {
    const url = src?.url || src?.metadata?.url;
    const label = src?.source_file || src?.doc_id || "Citation";
    if (!url || url === "N/A") {
      setActiveCitation({ title: label, content: "No source URL available for this citation." });
      return;
    }
    setActiveCitation({ title: label, content: "" });
    setCitationLoading(true);
    try {
      const res = await fetchCitationContent(url);
      const data = res.data || {};
      setActiveCitation({
        title: data.title || label,
        content: data.content || data.error || "No content available.",
      });
    } catch {
      setActiveCitation({ title: label, content: "Failed to load citation content." });
    } finally {
      setCitationLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await askQuestion(input, 5, undefined, "all", undefined, conversationId);
      const data = response.data;
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer, sources: data.sources },
      ]);
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.messages}>
        {messages.length === 0 && (
          <div className={styles.emptyState}>
            <div className={styles.emptyIcon}>
              <ChatBubblesQuestion24Regular style={{ color: tokens.colorNeutralForeground3 }} />
            </div>
            <Subtitle2>Ask your data anything</Subtitle2>
            <Caption1 style={{ color: tokens.colorNeutralForeground3 }}>Try a question:</Caption1>
            <div className={styles.chips}>
              {[
                "What are the top issues?",
                "Summarize the key themes",
                "Which products are mentioned most?",
                "Show billing-related problems",
              ].map((q, i) => (
                <button key={i} className={styles.chip} onClick={() => { setInput(q); }}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          msg.role === "user" ? (
            <div key={i} className={styles.userMsg}>
              <Body1>{msg.content}</Body1>
            </div>
          ) : (
            <div key={i} className={styles.assistantMsgWrap}>
              <div className={styles.assistantMsg}>
                {renderMarkdown(msg.content, (n: number) => { const src = (msg.sources || [])[n - 1]; if (src) openCitation(src); })}
                {msg.sources && msg.sources.length > 0 && (
                  <div className={styles.sources}>
                    <Caption1 style={{ color: "#94a3b8" }}>Sources:</Caption1>
                    {msg.sources.map((src, j) => (
                      <button
                        key={j}
                        type="button"
                        className={styles.sourceLink}
                        onClick={() => openCitation(src)}
                        title={src.source_file || src.doc_id}
                      >
                        {src.source_file || src.doc_id}
                      </button>
                    ))}
                  </div>
                )}
                <div className={styles.msgDisclaimer}>AI-generated content may be incorrect</div>
              </div>
            </div>
          )
        ))}
        {loading && (
          <div className={styles.assistantMsgWrap}>
            <div className={styles.assistantMsg}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, color: "#9ca3af", fontSize: 14 }}>
                <span style={{ animation: "pulse 1.5s ease-in-out infinite" }}>●</span>
                <span style={{ animation: "pulse 1.5s ease-in-out 0.3s infinite" }}>●</span>
                <span style={{ animation: "pulse 1.5s ease-in-out 0.6s infinite" }}>●</span>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
      <div className={styles.inputRow}>
        <ChatBubblesQuestion24Regular style={{ color: "#6366f1", flexShrink: 0 }} />
        <Input
          size="small"
          style={{ flex: 1 }}
          placeholder="Ask a question..."
          value={input}
          onChange={(_, data) => setInput(data.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <Button appearance="transparent" size="small" icon={<Send24Regular />}
          style={{ color: input.trim() ? "#6366f1" : "#d1d5db" }}
          onClick={handleSend} disabled={loading} />
      </div>

      {activeCitation && (
        <>
          <div className={styles.overlay} onClick={() => setActiveCitation(null)} />
          <div className={styles.drawer}>
            <div className={styles.drawerHeader}>
              Citation
              <button onClick={() => setActiveCitation(null)}
                style={{ border: "none", background: "none", cursor: "pointer", color: "#94a3b8", display: "flex" }}>
                <Dismiss20Regular />
              </button>
            </div>
            <div className={styles.drawerBody}>
              <h5 style={{ margin: "0 0 10px", fontSize: 13, color: "#0f172a", wordBreak: "break-all" }}>
                {activeCitation.title}
              </h5>
              {citationLoading ? (
                <div style={{ color: "#94a3b8", fontSize: 14 }}>Loading…</div>
              ) : (
                <div style={{ fontSize: 14, lineHeight: 1.75, color: "#334155", wordBreak: "break-word" }}>
                  {renderMarkdown(activeCitation.content)}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default ChatInterface;
