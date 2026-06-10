import React, { useState, useRef, useEffect } from "react";
import {
  Text,
  Button,
  Spinner,
} from "@fluentui/react-components";
import {
  ArrowUpload24Regular,
  CheckmarkCircle24Regular,
  ErrorCircle24Regular,
  Search24Regular,
  ChartMultiple24Regular,
  Database24Regular,
  LightbulbFilament20Regular,
  ChatBubblesQuestion20Regular,
  TextBulletListSquare20Regular,
} from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";
import {
  uploadJsonFile,
  uploadDocument,
  listDataSources,
  getUploadedFiles,
} from "../api/client";
import { FILE_TYPES } from "../utils/constants";
import { useAppState } from "../context/AppStateContext";
import s from "./Home.module.css";

/* ── Component ── */
const Home: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { setDashboardHeadline, setInsights } = useAppState();

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadDone, setUploadDone] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [dataSources, setDataSources] = useState<any[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [loadingSources, setLoadingSources] = useState(true);

  const loadStatus = () => {
    Promise.allSettled([listDataSources(), getUploadedFiles()])
      .then(([srcRes, filesRes]) => {
        const sources = srcRes.status === "fulfilled" ? srcRes.value.data || [] : [];
        const files = filesRes.status === "fulfilled" ? filesRes.value.data || [] : [];
        setDataSources(sources);
        setUploadedFiles(files);
        if (sources.length > 0 && sources[0].name) {
          setDashboardHeadline(sources[0].name);
        }
        // Clear insights cache if no data exists (data was cleared)
        if (sources.length === 0 && files.length === 0) {
          setInsights(null);
          try { sessionStorage.removeItem("km_insights"); } catch {}
        }
      })
      .finally(() => setLoadingSources(false));
  };

  useEffect(() => { loadStatus(); }, []);

  // Auto-refresh while any file is still processing
  const processingFiles = uploadedFiles.filter((f: any) => f.status === "processing");
  const readyFiles = uploadedFiles.filter((f: any) => f.status !== "processing");
  useEffect(() => {
    if (processingFiles.length === 0) return;
    const interval = setInterval(loadStatus, 5000);
    return () => clearInterval(interval);
  }, [processingFiles.length]);

  const uploadedFileCount = uploadedFiles.length;
  const totalRecords = dataSources.reduce((sum: number, ds: any) => sum + (ds.doc_count || 0), 0);
  const hasData = dataSources.length > 0 || uploadedFileCount > 0;

  const buildSummary = () => {
    const parts: string[] = [];
    if (totalRecords > 0) parts.push(`${totalRecords.toLocaleString()} records`);
    if (dataSources.length > 0) {
      const types = dataSources.map((ds: any) => ds.source_type);
      parts.push(types.join(" + "));
    }
    if (uploadedFileCount > 0) parts.push(`${uploadedFileCount} ${uploadedFileCount === 1 ? "document" : "documents"}`);
    return parts.join(" \u00b7 ");
  };

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
        await uploadDocument(files);
        setUploadMsg(`${files.length} file(s) submitted — processing in background`);
      }
      setUploadDone(true);
      setInsights(null); // Invalidate insights cache so it regenerates with new data
      loadStatus();
    } catch (err: unknown) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
            Upload additional documents to enrich your knowledge base.
          </div>
        </div>

        {/* Active Dataset card */}
        <div className={s.sourceCard}>
          {loadingSources ? (
            <Spinner size="small" />
          ) : hasData ? (
            <>
              <div className={s.sourceLabel}>Active Dataset</div>
              <Text size={300} style={{ color: "#64748b" }}>
                {buildSummary()}
              </Text>
              {/* File status list */}
              {uploadedFiles.length > 0 && (
                <div className={s.fileStatusList}>
                  {uploadedFiles.map((f: any) => (
                    <div key={f.id} className={s.fileStatusItem}>
                      <span className={s.fileStatusName}>{f.filename}</span>
                      {f.status === "processing" && (
                        <span className={s.fileStatusBadge} style={{ color: "#f59e0b", background: "#fef3c7" }}>
                          Processing
                        </span>
                      )}
                      {f.status === "failed" && (
                        <span className={s.fileStatusBadge} style={{ color: "#dc2626", background: "#fee2e2" }}
                          title={f.error || "Processing failed"}>
                          Failed
                        </span>
                      )}
                      {(f.status === "ready" || !f.status) && (
                        <span className={s.fileStatusBadge} style={{ color: "#059669", background: "#d1fae5" }}>
                          Ready
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                <Button appearance="primary" size="medium" icon={<ChartMultiple24Regular />}
                  onClick={() => navigate("/insights")}>View insights</Button>
                <Button appearance="outline" size="medium" icon={<Search24Regular />}
                  onClick={() => navigate("/explore")}>Explore data</Button>
              </div>
            </>
          ) : (
            <>
              <Database24Regular style={{ color: "#94a3b8", fontSize: 24 }} />
              <Text weight="semibold" size={400} style={{ color: "#64748b" }}>
                No data loaded yet
              </Text>
              <Text size={200} style={{ color: "#94a3b8" }}>
                Upload files to get started, or run a scenario pack from the command line.
              </Text>
              <Button
                appearance="primary"
                size="medium"
                icon={<ArrowUpload24Regular />}
                onClick={() => fileInputRef.current?.click()}
              >
                Upload files
              </Button>
            </>
          )}
        </div>

        {/* Upload card */}
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
            <>
              <div className={s.uploadIcon}>
                <ArrowUpload24Regular style={{ color: "#2563eb", fontSize: 24 }} />
              </div>
              <Text weight="semibold" size={400} style={{ color: "#0f172a" }}>
                Upload additional documents
              </Text>
              <Text size={200} style={{ color: "#94a3b8" }}>Drag & drop or click to browse</Text>
              <div className={s.fileTypes}>
                {FILE_TYPES.map((ft) => <span key={ft} className={s.fileType}>{ft}</span>)}
              </div>
            </>
          )}

          <input ref={fileInputRef} type="file" multiple style={{ display: "none" }}
            accept=".json,.csv,.pdf,.docx,.xlsx,.txt,.png,.jpg,.jpeg,.tiff,.bmp,.wav,.mp3,.mp4" onChange={handleUpload} />
        </div>
      </div>

      <div className={s.content}>
        {/* Getting started section — shown when no data exists */}
        {!hasData && (
          <div>
            <div className={s.sectionLabel}>Getting started</div>
            <div className={s.valueGrid}>
              <div className={s.valueCard} style={{ cursor: "pointer" }} onClick={() => fileInputRef.current?.click()}>
                <div className={s.valueIcon} style={{ backgroundColor: "#dbeafe" }}>
                  <ArrowUpload24Regular style={{ color: "#2563eb" }} />
                </div>
                <div className={s.valueTitle}>Upload files</div>
                <div className={s.valueDesc}>Drag & drop PDFs, Word docs, JSON, CSV, images, or audio files. They'll be processed automatically.</div>
              </div>
              <div className={s.valueCard}>
                <div className={s.valueIcon} style={{ backgroundColor: "#d1fae5" }}>
                  <TextBulletListSquare20Regular style={{ color: "#059669" }} />
                </div>
                <div className={s.valueTitle}>Load a scenario pack</div>
                <div className={s.valueDesc}>Run <code style={{ fontSize: 11 }}>./scripts/setup-data.ps1</code> to load a built-in scenario or connect an external data source.</div>
              </div>
            </div>
          </div>
        )}

        {/* Value section — shown when data already exists */}
        {hasData && (
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
        )}
      </div>

    </div>
  );
};

export default Home;
