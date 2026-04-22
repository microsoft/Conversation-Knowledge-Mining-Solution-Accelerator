import React, { useState, useRef, useEffect } from "react";
import {
  makeStyles,
  tokens,
  Input,
  Button,
  Body1,
  Subtitle2,
  Caption1,
  Spinner,
  Badge,
} from "@fluentui/react-components";
import { Send24Regular, ChatBubblesQuestion24Regular } from "@fluentui/react-icons";
import { askQuestion } from "../api/client";

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
    backgroundColor: tokens.colorBrandBackground,
    color: tokens.colorNeutralForegroundOnBrand,
    padding: "12px 16px",
    borderRadius: "16px 16px 4px 16px",
    maxWidth: "82%",
    fontSize: tokens.fontSizeBase300,
    lineHeight: tokens.lineHeightBase300,
    boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
  },
  assistantMsg: {
    alignSelf: "flex-start",
    backgroundColor: tokens.colorNeutralBackground3,
    padding: "14px 18px",
    borderRadius: "16px 16px 16px 4px",
    maxWidth: "82%",
    fontSize: tokens.fontSizeBase300,
    lineHeight: tokens.lineHeightBase400,
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
    whiteSpace: "pre-wrap" as const,
    wordBreak: "break-word" as const,
  },
  inputRow: {
    display: "flex",
    gap: "6px",
    padding: "12px 16px",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  sources: { marginTop: "8px", display: "flex", flexWrap: "wrap", gap: "4px" },
  disclaimer: {
    textAlign: "center" as const,
    padding: "6px",
    fontSize: "10px",
    color: "#b0b0b0",
    flexShrink: 0,
  },
});

interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ doc_id: string; score: number }>;
}

const ChatInterface: React.FC = () => {
  const styles = useStyles();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await askQuestion(input);
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
          <div key={i} className={msg.role === "user" ? styles.userMsg : styles.assistantMsg}>
            <Body1>{msg.content}</Body1>
            {msg.sources && msg.sources.length > 0 && (
              <div className={styles.sources}>
                {msg.sources.map((s, j) => (
                  <Badge key={j} appearance="outline" size="small" shape="rounded">
                    {s.doc_id} ({s.score.toFixed(2)})
                  </Badge>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && <Spinner size="tiny" label="Thinking..." style={{ alignSelf: "flex-start", padding: "8px" }} />}
        <div ref={messagesEndRef} />
      </div>
      <div className={styles.inputRow}>
        <Input
          size="small"
          style={{ flex: 1 }}
          placeholder="Ask a question..."
          value={input}
          onChange={(_, data) => setInput(data.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <Button appearance="primary" size="small" icon={<Send24Regular />} onClick={handleSend} disabled={loading} />
      </div>
      <div className={styles.disclaimer}>AI-generated content may be incorrect</div>
    </div>
  );
};

export default ChatInterface;
