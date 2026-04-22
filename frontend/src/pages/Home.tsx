import React, { useState, useEffect, useRef } from "react";
import {
  Text,
  Button,
  makeStyles,
  Spinner,
  Input,
} from "@fluentui/react-components";
import {
  ArrowUpload24Regular,
  CheckmarkCircle24Regular,
  ErrorCircle24Regular,
  Search24Regular,
  ChartMultiple24Regular,
  Sparkle20Regular,
  DocumentText20Regular,
  Database20Regular,
  LightbulbFilament20Regular,
  ChatBubblesQuestion20Regular,
  TextBulletListSquare20Regular,
} from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";
import {
  loadDefaultDataset,
  uploadJsonFile,
  uploadDocument,
  getUploadedFiles,
  connectExternalIndex,
} from "../api/client";

/* ── Styles ── */
const useStyles = makeStyles({
  page: {
    overflowY: "auto",
    height: "100%",
    backgroundColor: "#f9fafb",
  },

  /* Hero — stacked: text on top, upload below */
  hero: {
    display: "flex",
    flexDirection: "column",
    gap: "32px",
    alignItems: "center",
    maxWidth: "1060px",
    margin: "0 auto",
    padding: "56px 40px 0",
  },
  heroLeft: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
    textAlign: "center" as const,
    alignItems: "center",
  },
  heroTitle: {
    fontSize: "28px",
    fontWeight: "700",
    color: "#0f172a",
    lineHeight: "1.25",
    letterSpacing: "-0.5px",
  },
  heroSub: {
    fontSize: "15px",
    color: "#64748b",
    lineHeight: "1.7",
    maxWidth: "500px",
    textAlign: "center" as const,
  },
  heroCtas: {
    display: "flex",
    gap: "10px",
    alignItems: "center",
    flexWrap: "wrap" as const,
    marginTop: "4px",
  },
  connectLink: {
    fontSize: "13px",
    color: "#2563eb",
    cursor: "pointer",
    fontWeight: "500",
    marginLeft: "4px",
    border: "none",
    background: "none",
    fontFamily: "inherit",
    padding: 0,
  },

  /* Upload card — full width below hero text */
  uploadCard: {
    width: "100%",
    maxWidth: "640px",
    padding: "56px 40px",
    borderRadius: "24px",
    border: "2px dashed #d1d5db",
    backgroundColor: "#ffffff",
    textAlign: "center" as const,
    cursor: "pointer",
    transition: "border-color 0.2s, box-shadow 0.2s, transform 0.15s",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "16px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  uploadIcon: {
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, #dbeafe 0%, #e0e7ff 100%)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  fileTypes: {
    display: "flex",
    gap: "6px",
    flexWrap: "wrap" as const,
    justifyContent: "center",
    marginTop: "4px",
  },
  fileType: {
    fontSize: "10px",
    padding: "3px 8px",
    borderRadius: "4px",
    backgroundColor: "#f1f5f9",
    color: "#64748b",
    fontWeight: "600",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },

  /* Content sections */
  content: {
    maxWidth: "1060px",
    margin: "0 auto",
    padding: "40px 40px 60px",
    display: "flex",
    flexDirection: "column",
    gap: "40px",
  },

  /* Value section */
  sectionLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#94a3b8",
    textTransform: "uppercase" as const,
    letterSpacing: "1.2px",
    marginBottom: "4px",
  },
  valueGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: "16px",
  },
  valueCard: {
    padding: "24px",
    borderRadius: "16px",
    backgroundColor: "#ffffff",
    border: "1px solid #f1f5f9",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    transition: "box-shadow 0.2s, transform 0.15s",
    cursor: "default",
  },
  valueIcon: {
    width: "40px",
    height: "40px",
    borderRadius: "12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  valueTitle: {
    fontSize: "15px",
    fontWeight: "600",
    color: "#0f172a",
  },
  valueDesc: {
    fontSize: "13px",
    color: "#64748b",
    lineHeight: "1.55",
  },

  /* Quick start cards */
  quickGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "16px",
  },
  quickCard: {
    padding: "22px 24px",
    borderRadius: "16px",
    backgroundColor: "#ffffff",
    border: "1px solid #e5e7eb",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    transition: "box-shadow 0.2s, transform 0.15s",
  },
  quickIcon: {
    width: "44px",
    height: "44px",
    borderRadius: "12px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    flexShrink: 0,
  },

  /* Recent work */
  recentGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: "14px",
  },
  recentCard: {
    padding: "20px",
    borderRadius: "16px",
    backgroundColor: "#ffffff",
    border: "1px solid #f1f5f9",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    transition: "box-shadow 0.2s",
    cursor: "default",
  },
  recentName: {
    fontSize: "14px",
    fontWeight: "600",
    color: "#0f172a",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
  },
  recentMeta: {
    fontSize: "12px",
    color: "#94a3b8",
  },
  recentActions: {
    display: "flex",
    gap: "6px",
    marginTop: "auto",
  },

  /* Ready card */
  readyCard: {
    maxWidth: "1060px",
    margin: "0 auto",
    padding: "0 40px",
  },
  readyInner: {
    borderRadius: "20px",
    backgroundColor: "#ffffff",
    boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 0 0 1px rgba(0,0,0,0.02)",
    padding: "32px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    marginTop: "48px",
  },
  readyHeader: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
  },
  bullets: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  bullet: {
    fontSize: "14px",
    color: "#475569",
    lineHeight: "1.7",
  },
  detected: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    flexWrap: "wrap" as const,
    paddingTop: "12px",
    borderTop: "1px solid #f1f5f9",
  },
  detectedLabel: {
    fontSize: "11px",
    fontWeight: "700",
    color: "#94a3b8",
    textTransform: "uppercase" as const,
    letterSpacing: "0.8px",
  },
  detectedTag: {
    fontSize: "12px",
    padding: "4px 12px",
    borderRadius: "8px",
    backgroundColor: "#f1f5f9",
    color: "#475569",
    fontWeight: "500",
  },
  nextSteps: {
    display: "flex",
    gap: "12px",
    paddingTop: "4px",
  },
  intentWrap: {
    display: "flex",
    flexDirection: "column",
    gap: "12px",
    marginTop: "4px",
  },
  suggestions: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap" as const,
  },
  suggestion: {
    padding: "7px 16px",
    borderRadius: "20px",
    border: "1px solid #e5e7eb",
    backgroundColor: "#ffffff",
    fontSize: "13px",
    color: "#64748b",
    cursor: "pointer",
    fontFamily: "inherit",
    transition: "all 0.15s",
  },
  uploadAnother: {
    fontSize: "13px",
    color: "#94a3b8",
    cursor: "pointer",
    textAlign: "center" as const,
    fontWeight: "500",
    marginTop: "4px",
  },

  /* Connect form */
  connectForm: {
    padding: "28px",
    borderRadius: "16px",
    backgroundColor: "#ffffff",
    border: "1px solid #e5e7eb",
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },

  /* Error */
  errorCard: {
    maxWidth: "1060px",
    margin: "48px auto 0",
    padding: "0 40px",
  },
  errorInner: {
    padding: "22px 28px",
    borderRadius: "16px",
    backgroundColor: "#ffffff",
    border: "1px solid #fecaca",
    display: "flex",
    alignItems: "center",
    gap: "16px",
  },
});

const SUGGESTIONS = ["Summarize this report", "Extract key metrics", "Find trends"];
const FILE_TYPES = ["PDF", "DOCX", "JSON", "CSV", "XLSX", "PNG", "JPG", "TXT"];

/* ── Component ── */
const Home: React.FC = () => {
  const s = useStyles();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [state, setState] = useState<"upload" | "ready" | "error">("upload");
  const [quickInsights, setQuickInsights] = useState<{
    summary: string; highlights: string[]; detected: string[]; keywords: string[];
  } | null>(null);
  const [intent, setIntent] = useState("");
  const [recentFiles, setRecentFiles] = useState<
    Array<{ id: string; filename: string; doc_count: number; summary: string }>
  >([]);
  const [showConnect, setShowConnect] = useState(false);
  const [connectEndpoint, setConnectEndpoint] = useState("");
  const [connectIndex, setConnectIndex] = useState("");
  const [connectTextField, setConnectTextField] = useState("content");
  const [connecting, setConnecting] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  useEffect(() => {
    getUploadedFiles().then((r) => setRecentFiles(r.data)).catch(() => {});
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const label = files.length === 1 ? files[0].name : `${files.length} files`;
    setUploading(true);
    setUploadMsg(`Analyzing ${label}...`);
    setQuickInsights(null);
    try {
      if (files.length === 1 && files[0].name.toLowerCase().endsWith(".json")) {
        const res = await uploadJsonFile(files[0]);
        setUploadMsg(`${res.data.total_loaded} records loaded`);
        if (res.data.quick_insights) setQuickInsights(res.data.quick_insights);
      } else {
        const res = await uploadDocument(files);
        setUploadMsg(`${res.data.total_loaded} documents processed`);
        if (res.data.quick_insights) setQuickInsights(res.data.quick_insights);
      }
      setState("ready");
      getUploadedFiles().then((r) => setRecentFiles(r.data)).catch(() => {});
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "Upload failed");
      setState("error");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDemo = async () => {
    setUploading(true);
    setUploadMsg("Loading sample data...");
    setQuickInsights(null);
    try {
      const res = await loadDefaultDataset();
      setUploadMsg(`${res.data.total_loaded} documents loaded`);
      setState("ready");
      getUploadedFiles().then((r) => setRecentFiles(r.data)).catch(() => {});
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "Load failed");
      setState("error");
    } finally {
      setUploading(false);
    }
  };

  const handleConnect = async () => {
    if (!connectEndpoint.trim() || !connectIndex.trim()) return;
    setConnecting(true);
    try {
      const res = await connectExternalIndex({
        name: connectIndex,
        endpoint: connectEndpoint.trim(),
        index_name: connectIndex.trim(),
        text_field: connectTextField.trim() || "content",
      });
      setUploadMsg(`Connected — ${res.data.doc_count} documents`);
      setState("ready");
      setShowConnect(false);
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "Connection failed");
      setState("error");
    } finally {
      setConnecting(false);
    }
  };

  const reset = () => { setState("upload"); setQuickInsights(null); setUploadMsg(""); };

  /* ── Upload State ── */
  if (state === "upload") {
    return (
      <div className={s.page}>
        {/* Hero — 2 columns */}
        <div className={s.hero}>
          <div className={s.heroLeft}>
            <div className={s.heroTitle}>Turn your data into answers and insights</div>
            <div className={s.heroSub}>
              Upload documents, connect a data source, or try a demo — then explore through chat and AI-generated reports.
            </div>
          </div>

          {/* Upload card */}
          <div
            className={s.uploadCard}
            onClick={() => !uploading && fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault(); setDragOver(false);
              if (e.dataTransfer.files.length > 0 && fileInputRef.current) {
                fileInputRef.current.files = e.dataTransfer.files;
                fileInputRef.current.dispatchEvent(new Event("change", { bubbles: true }));
              }
            }}
            style={dragOver ? { borderColor: "#2563eb", boxShadow: "0 0 0 4px rgba(37,99,235,0.1)", transform: "scale(1.01)" } : undefined}
          >
            <div className={s.uploadIcon}>
              {uploading ? <Spinner size="small" /> : <ArrowUpload24Regular style={{ color: "#2563eb", fontSize: 24 }} />}
            </div>
            <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>
              {uploading ? uploadMsg : "Upload your data to get started"}
            </Text>
            <Text size={200} style={{ color: "#94a3b8" }}>Drag & drop or click to browse</Text>
            <div className={s.fileTypes}>
              {FILE_TYPES.map((ft) => <span key={ft} className={s.fileType}>{ft}</span>)}
            </div>
            <input ref={fileInputRef} type="file" multiple style={{ display: "none" }}
              accept=".json,.csv,.pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg,.tiff,.bmp" onChange={handleUpload} />
          </div>
        </div>

        {/* Connect form (expandable) */}
        {showConnect && (
          <div style={{ maxWidth: 1060, margin: "0 auto", padding: "24px 40px 0" }}>
            <div className={s.connectForm}>
              <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>Connect to existing Azure AI Search index</Text>
              <Input size="medium" placeholder="Search endpoint (https://...search.windows.net)"
                value={connectEndpoint} onChange={(_, d) => setConnectEndpoint(d.value)} />
              <Input size="medium" placeholder="Index name"
                value={connectIndex} onChange={(_, d) => setConnectIndex(d.value)} />
              <Input size="medium" placeholder="Text field name (default: content)"
                value={connectTextField} onChange={(_, d) => setConnectTextField(d.value)} />
              <div style={{ display: "flex", gap: 8 }}>
                <Button appearance="primary" size="medium" onClick={handleConnect}
                  disabled={connecting || !connectEndpoint || !connectIndex}>
                  {connecting ? "Connecting..." : "Connect"}
                </Button>
                <Button appearance="subtle" size="medium" onClick={() => setShowConnect(false)}>Cancel</Button>
              </div>
            </div>
          </div>
        )}

        <div className={s.content}>
          {/* Value section */}
          <div>
            <div className={s.sectionLabel}>What you can do</div>
            <div className={s.valueGrid}>
              <div className={s.valueCard}>
                <div className={s.valueIcon} style={{ backgroundColor: "#dbeafe" }}>
                  <LightbulbFilament20Regular style={{ color: "#2563eb" }} />
                </div>
                <div className={s.valueTitle}>Extract insights</div>
                <div className={s.valueDesc}>Get AI-generated summaries, key findings, metrics, trends, and risk analysis from any document.</div>
              </div>
              <div className={s.valueCard}>
                <div className={s.valueIcon} style={{ backgroundColor: "#f3e8ff" }}>
                  <ChatBubblesQuestion20Regular style={{ color: "#7c3aed" }} />
                </div>
                <div className={s.valueTitle}>Ask questions</div>
                <div className={s.valueDesc}>Chat with your data using natural language. Filter by document, type, or topic to scope your queries.</div>
              </div>
              <div className={s.valueCard}>
                <div className={s.valueIcon} style={{ backgroundColor: "#d1fae5" }}>
                  <TextBulletListSquare20Regular style={{ color: "#059669" }} />
                </div>
                <div className={s.valueTitle}>Structure outputs</div>
                <div className={s.valueDesc}>Extract entities, key phrases, and structured data. Export reports as JSON for downstream use.</div>
              </div>
            </div>
          </div>

          {/* Quick start */}
          <div>
            <div className={s.sectionLabel}>Quick start</div>
            <div className={s.quickGrid}>
              <div className={s.quickCard} onClick={handleDemo} style={uploading ? { opacity: 0.5 } : undefined}>
                <div className={s.quickIcon} style={{ backgroundColor: "#fef3c7" }}>
                  <DocumentText20Regular style={{ color: "#d97706" }} />
                </div>
                <div>
                  <Text weight="semibold" size={300} style={{ color: "#0f172a" }}>Try demo dataset</Text>
                  <Text block size={200} style={{ color: "#94a3b8", marginTop: 2 }}>
                    60 customer service documents — chats, tickets, FAQs
                  </Text>
                </div>
              </div>
              <div className={s.quickCard} onClick={() => setShowConnect(true)}>
                <div className={s.quickIcon} style={{ backgroundColor: "#dbeafe" }}>
                  <Database20Regular style={{ color: "#2563eb" }} />
                </div>
                <div>
                  <Text weight="semibold" size={300} style={{ color: "#0f172a" }}>Connect data source</Text>
                  <Text block size={200} style={{ color: "#94a3b8", marginTop: 2 }}>
                    Point at an existing Azure AI Search index
                  </Text>
                </div>
              </div>
            </div>
          </div>

          {/* Recent work */}
          {recentFiles.length > 0 && (
            <div>
              <div className={s.sectionLabel}>Continue where you left off</div>
              <div className={s.recentGrid}>
                {recentFiles.slice(0, 6).map((f) => (
                  <div key={f.id} className={s.recentCard}>
                    <div className={s.recentName}>{f.filename}</div>
                    <div className={s.recentMeta}>{f.doc_count} records</div>
                    <div className={s.recentActions}>
                      <Button appearance="subtle" size="small" onClick={() => navigate("/explore")}>Explore</Button>
                      <Button appearance="subtle" size="small" onClick={() => navigate("/insights")}>Insights</Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  /* ── Ready State ── */
  if (state === "ready") {
    return (
      <div className={s.page}>
        <div className={s.readyCard}>
          <div className={s.readyInner}>
            <div className={s.readyHeader}>
              <CheckmarkCircle24Regular style={{ color: "#059669", fontSize: 24 }} />
              <Text weight="semibold" size={500} style={{ color: "#0f172a" }}>Your data is ready</Text>
            </div>

            {quickInsights && quickInsights.highlights.length > 0 && (
              <div>
                <Text size={200} weight="semibold" style={{ color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.8px" }}>
                  Quick Insights
                </Text>
                <div className={s.bullets} style={{ marginTop: 8 }}>
                  {quickInsights.highlights.map((h, i) => <div key={i} className={s.bullet}>• {h}</div>)}
                </div>
              </div>
            )}

            {!quickInsights && <Text size={300} style={{ color: "#475569" }}>{uploadMsg}</Text>}

            <div className={s.nextSteps}>
              <Button appearance="primary" size="medium" icon={<Search24Regular />} onClick={() => navigate("/explore")}>
                Explore data
              </Button>
              <Button appearance="outline" size="medium" icon={<ChartMultiple24Regular />} onClick={() => navigate("/insights")}>
                View insights
              </Button>
            </div>

            <div className={s.intentWrap}>
              <Input size="large" placeholder="Ask a question about your data..."
                contentBefore={<Sparkle20Regular style={{ color: "#2563eb" }} />}
                value={intent} onChange={(_, d) => setIntent(d.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && intent.trim()) navigate(`/explore?q=${encodeURIComponent(intent)}`); }}
                style={{ borderRadius: 12 }} />
              <div className={s.suggestions}>
                {SUGGESTIONS.map((s2) => (
                  <span key={s2} className={s.suggestion} onClick={() => navigate(`/explore?q=${encodeURIComponent(s2)}`)}>{s2}</span>
                ))}
              </div>
            </div>

            <div className={s.uploadAnother} onClick={reset}>Upload another file</div>
          </div>
        </div>
      </div>
    );
  }

  /* ── Error State ── */
  return (
    <div className={s.page}>
      <div className={s.errorCard}>
        <div className={s.errorInner}>
          <ErrorCircle24Regular style={{ color: "#dc2626", flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <Text weight="semibold" size={300}>Upload failed</Text>
            <Text block size={200} style={{ color: "#dc2626", marginTop: 2 }}>{uploadMsg}</Text>
          </div>
          <Button appearance="subtle" size="small" onClick={reset}>Try again</Button>
        </div>
      </div>
    </div>
  );
};

export default Home;
