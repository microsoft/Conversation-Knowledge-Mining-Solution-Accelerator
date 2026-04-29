import React, { useState, useRef, useEffect } from "react";
import {
  Text,
  Button,
  makeStyles,
  Spinner,
} from "@fluentui/react-components";
import {
  ArrowUpload24Regular,
  CheckmarkCircle24Regular,
  ErrorCircle24Regular,
  Search24Regular,
  ChartMultiple24Regular,
  DocumentText20Regular,
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
} from "../api/client";
import { FILE_TYPES } from "../utils/constants";

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

  /* Recent work — compact table */
  recentGrid: {
    display: "flex",
    flexDirection: "column",
    gap: "0px",
    borderRadius: "12px",
    border: "1px solid #e2e8f0",
    backgroundColor: "#ffffff",
    overflow: "hidden",
  },
  recentCard: {
    padding: "12px 20px",
    display: "flex",
    alignItems: "center",
    gap: "16px",
    borderBottom: "1px solid #f1f5f9",
    transition: "background 0.12s",
    cursor: "default",
    ":last-child": { borderBottom: "none" },
  },
  recentName: {
    fontSize: "13px",
    fontWeight: "600",
    color: "#0f172a",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap" as const,
    flex: 1,
    minWidth: 0,
  },
  recentMeta: {
    fontSize: "12px",
    color: "#94a3b8",
    whiteSpace: "nowrap" as const,
    flexShrink: 0,
  },
  recentActions: {
    display: "flex",
    gap: "4px",
    flexShrink: 0,
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

/* ── Component ── */
const Home: React.FC = () => {
  const s = useStyles();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadDone, setUploadDone] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [existingDocCount, setExistingDocCount] = useState(0);

  useEffect(() => {
    getUploadedFiles()
      .then((r) => setExistingDocCount(r.data?.length || 0))
      .catch(() => {});
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files = Array.from(fileList);
    const label = files.length === 1 ? files[0].name : `${files.length} files`;
    setUploading(true);
    setUploadDone(false);
    setUploadError("");
    setUploadMsg(`Uploading ${label}...`);
    try {
      if (files.length === 1 && files[0].name.toLowerCase().endsWith(".json")) {
        const res = await uploadJsonFile(files[0]);
        setUploadMsg(`${res.data.total_loaded} records loaded`);
      } else {
        const res = await uploadDocument(files);
        setUploadMsg(`${res.data.total_loaded} documents uploaded`);
      }
      setUploadDone(true);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleDemo = async () => {
    setUploading(true);
    setUploadDone(false);
    setUploadError("");
    setUploadMsg("Loading sample data...");
    try {
      const res = await loadDefaultDataset();
      setUploadMsg(`${res.data.total_loaded} documents loaded`);
      setUploadDone(true);
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Load failed");
    } finally {
      setUploading(false);
    }
  };

  const resetUpload = () => {
    setUploadDone(false);
    setUploadError("");
    setUploadMsg("");
  };

  return (
    <div className={s.page}>
      {/* Hero */}
      <div className={s.hero}>
        <div className={s.heroLeft}>
          <div className={s.heroTitle}>Turn your data into answers and insights</div>
          <div className={s.heroSub}>
            Upload documents, connect a data source, or try a demo — then explore through chat and AI-generated reports.
          </div>
        </div>

        {/* Upload card — all states in one box */}
        <div
          className={s.uploadCard}
          onClick={() => !uploading && !uploadDone && fileInputRef.current?.click()}
          onDragOver={(e) => { if (!uploadDone) { e.preventDefault(); setDragOver(true); } }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault(); setDragOver(false);
            if (!uploadDone && e.dataTransfer.files.length > 0 && fileInputRef.current) {
              fileInputRef.current.files = e.dataTransfer.files;
              fileInputRef.current.dispatchEvent(new Event("change", { bubbles: true }));
            }
          }}
          style={{
            ...(dragOver ? { borderColor: "#2563eb", boxShadow: "0 0 0 4px rgba(37,99,235,0.1)" } : {}),
            ...(uploadDone ? { cursor: "default", borderStyle: "solid", borderColor: "#bbf7d0" } : {}),
            ...(!uploading && !uploadDone && !uploadError && existingDocCount > 0
              ? { borderStyle: "solid", borderColor: "#bbf7d0", cursor: "pointer" }
              : {}),
          }}
        >
          {/* Uploading state */}
          {uploading && (
            <>
              <Spinner size="small" />
              <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>{uploadMsg}</Text>
              <Text size={200} style={{ color: "#94a3b8" }}>This may take a moment for large files</Text>
            </>
          )}

          {/* Success state */}
          {uploadDone && !uploading && (
            <>
              <CheckmarkCircle24Regular style={{ color: "#059669", fontSize: 28 }} />
              <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>{uploadMsg}</Text>
              <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                <Button appearance="primary" size="medium" icon={<Search24Regular />}
                  onClick={(e) => { e.stopPropagation(); navigate("/explore"); }}>Explore data</Button>
                <Button appearance="outline" size="medium" icon={<ChartMultiple24Regular />}
                  onClick={(e) => { e.stopPropagation(); navigate("/insights"); }}>View insights</Button>
              </div>
              <Text size={200} style={{ color: "#2563eb", cursor: "pointer", marginTop: 4 }}
                onClick={(e) => { e.stopPropagation(); resetUpload(); }}>
                Upload more files
              </Text>
            </>
          )}

          {/* Error state */}
          {uploadError && !uploading && (
            <>
              <ErrorCircle24Regular style={{ color: "#dc2626", fontSize: 28 }} />
              <Text weight="semibold" size={300} style={{ color: "#dc2626" }}>{uploadError}</Text>
              <Button appearance="subtle" size="small" onClick={(e) => { e.stopPropagation(); resetUpload(); }}>
                Try again
              </Button>
            </>
          )}

          {/* Default state */}
          {!uploading && !uploadDone && !uploadError && (
            existingDocCount > 0 ? (
              <>
                <CheckmarkCircle24Regular style={{ color: "#059669", fontSize: 28 }} />
                <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>
                  {existingDocCount} {existingDocCount === 1 ? "file" : "files"} ready
                </Text>
                <div style={{ display: "flex", gap: 10, marginTop: 4 }}>
                  <Button appearance="primary" size="medium" icon={<Search24Regular />}
                    onClick={(e) => { e.stopPropagation(); navigate("/explore"); }}>Explore data</Button>
                  <Button appearance="outline" size="medium" icon={<ChartMultiple24Regular />}
                    onClick={(e) => { e.stopPropagation(); navigate("/insights"); }}>View insights</Button>
                </div>
                <Text size={200} style={{ color: "#94a3b8" }}>
                  or drop more files here to add data
                </Text>
              </>
            ) : (
              <>
                <div className={s.uploadIcon}>
                  <ArrowUpload24Regular style={{ color: "#2563eb", fontSize: 24 }} />
                </div>
                <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>
                  Upload your data to get started
                </Text>
                <Text size={200} style={{ color: "#94a3b8" }}>Drag & drop or click to browse</Text>
                <div className={s.fileTypes}>
                  {FILE_TYPES.map((ft) => <span key={ft} className={s.fileType}>{ft}</span>)}
                </div>
              </>
            )
          )}

          <input ref={fileInputRef} type="file" multiple style={{ display: "none" }}
            accept=".json,.csv,.pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg,.tiff,.bmp" onChange={handleUpload} />
        </div>
      </div>

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
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
