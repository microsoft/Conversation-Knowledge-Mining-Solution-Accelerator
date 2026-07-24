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
  refreshIngestionCache,
} from "../api/client";
import { getApiErrorMessage } from "../utils/errors";
import { FILE_TYPES, SUPPORTED_UPLOAD_ACCEPT, SUPPORTED_UPLOAD_DESCRIPTION } from "../utils/constants";
import { useAppState } from "../context/AppStateContext";
import uiConfig from "../config/ui-config.json";
import s from "./Home.module.css";

/* ── Component ── */
const Home: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { setDashboardHeadline, setInsights, homeData, setHomeData, ingestionSnapshot } = useAppState();
  const { setExploreData } = useAppState();

  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadDone, setUploadDone] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [dataSources, setDataSources] = useState<any[]>(homeData?.dataSources ?? []);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>(homeData?.uploadedFiles ?? []);
  // Only show spinner on first ever load (no cached data). Subsequent mounts refresh silently.
  const [loadingSources, setLoadingSources] = useState(!homeData);
  const refreshedCacheRef = useRef(false);

  const loadStatus = async () => {
    try {
      // Ensure seeded or externally changed data is reflected before listing sources/files.
      if (!refreshedCacheRef.current) {
        try {
          await refreshIngestionCache();
        } catch {
          // Continue with direct reads.
        }
        refreshedCacheRef.current = true;
      }

      const [filesRes, srcRes] = await Promise.allSettled([getUploadedFiles(), listDataSources()]);
      const files = filesRes.status === "fulfilled" && Array.isArray(filesRes.value.data) ? filesRes.value.data : [];
      const sources = srcRes.status === "fulfilled" && Array.isArray(srcRes.value.data) ? srcRes.value.data : [];

      setDataSources(sources);
      setUploadedFiles(files);
      setHomeData({ dataSources: sources, uploadedFiles: files });
      if (sources.length > 0 && sources[0].name) {
        setDashboardHeadline(sources[0].name);
      }
      if (sources.length === 0 && files.length === 0) {
        setInsights(null);
        try { sessionStorage.removeItem("km_insights"); } catch {}
      }
    } catch {
      // Never preserve stale list on failure.
      setDataSources([]);
      setUploadedFiles([]);
      setHomeData({ dataSources: [], uploadedFiles: [] });
    } finally {
      setLoadingSources(false);
    }
  };

  // Always refresh on mount to avoid stale session-cached sources.
  useEffect(() => { loadStatus(); }, []);

  // Shared app-level polling updates this page through ingestionSnapshot.
  useEffect(() => {
    if (!ingestionSnapshot) return;
    setUploadedFiles(Array.isArray(ingestionSnapshot.uploadedFiles) ? ingestionSnapshot.uploadedFiles : []);
    setDataSources(Array.isArray(ingestionSnapshot.dataSources) ? ingestionSnapshot.dataSources : []);
    setHomeData({
      uploadedFiles: Array.isArray(ingestionSnapshot.uploadedFiles) ? ingestionSnapshot.uploadedFiles : [],
      dataSources: Array.isArray(ingestionSnapshot.dataSources) ? ingestionSnapshot.dataSources : [],
    });
  }, [ingestionSnapshot]); // setHomeData is stable (useCallback) — omitting avoids stale-closure false dep

  const uploadedFileCount = uploadedFiles.length;
  const totalRecords = dataSources.reduce((sum: number, ds: any) => sum + (ds.doc_count || 0), 0);
  const hasData = dataSources.length > 0 || uploadedFileCount > 0;
  const failedCount = uploadedFiles.filter((f: any) => f.status === "failed").length;
  const chatReadyCount = uploadedFiles.filter((f: any) => f.status === "extracted").length;
  const readyCount = uploadedFiles.filter((f: any) => f.status === "ready" && (f.doc_count || 0) > 0).length;
  const processingCount = uploadedFileCount - readyCount - chatReadyCount - failedCount;
  const insightsAvailable = readyCount > 0 || dataSources.length > 0;

  const getFileStatusLabel = (status?: string) => {
    if (status === "processing") return "Processing";
    if (status === "extracted") return "Chat ready";
    if (status === "failed") return "Failed";
    return "Ready";
  };

  const getFileStatusStyle = (status?: string) => {
    if (status === "processing") return { color: "#f59e0b", background: "#fef3c7" };
    if (status === "extracted") return { color: "#2563eb", background: "#dbeafe" };
    if (status === "failed") return { color: "#dc2626", background: "#fee2e2" };
    return { color: "#059669", background: "#d1fae5" };
  };

  const toTitleCase = (value: string) =>
    value.replace(/\b([a-z])/g, (m) => m.toUpperCase());

  const formatFriendlyFileTitle = (filename?: string) => {
    if (!filename) return "My data";

    const base = filename.replace(/\.[^.]+$/, "");
    const ext = (filename.match(/\.([^.]+)$/)?.[1] || "").toUpperCase();

    const timestampMatch = base.match(/(20\d{2})[-_ ]?(\d{2})[-_ ]?(\d{2})(?:[ T_-]?(\d{2})[ _:-]?(\d{2})(?:[ _:-]?(\d{2}))?)?/);
    const timestampLabel = timestampMatch
      ? `${timestampMatch[1]}-${timestampMatch[2]}-${timestampMatch[3]}${timestampMatch[4] ? ` ${timestampMatch[4]}:${timestampMatch[5] || "00"}` : ""}`
      : "";

    let friendly = base
      .replace(/[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}/gi, "")
      .replace(/(20\d{2})[-_ ]?(\d{2})[-_ ]?(\d{2})(?:[ T_-]?(\d{2})[ _:-]?(\d{2})(?:[ _:-]?(\d{2}))?)?/g, "")
      .replace(/\bconvo\b/gi, "Conversation")
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();

    if (!friendly) {
      friendly = "Conversation";
    }

    friendly = toTitleCase(friendly);

    const title = timestampLabel ? `${friendly} ${timestampLabel}` : friendly;
    return ext ? `${title} (${ext})` : title;
  };

  const toFriendlyUseCaseName = (value?: string) => {
    if (!value) return "";
    const normalized = value
      .replace(/[_-]+/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return toTitleCase(normalized);
  };

  const getUseCaseDisplayTitle = () => {
    const firstSource = dataSources[0];
    const sourceName = toFriendlyUseCaseName(
      firstSource?.use_case ||
      firstSource?.display_name ||
      firstSource?.name ||
      (dataSources.length > 0 ? uiConfig?.useCaseName : undefined)
    );
    if (sourceName) {
      if (firstSource?.source_type && firstSource.source_type !== "native") {
        return `${sourceName} Connection`;
      }
      return `${sourceName} Dataset`;
    }
    return "My Data";
  };

  const isExternalConnectionCard = Boolean(
    dataSources[0]?.source_type && dataSources[0]?.source_type !== "native"
  );
  const primaryExternalSourceName = isExternalConnectionCard ? dataSources[0]?.name : undefined;

  const buildSummary = () => {
    const useCaseTitle = getUseCaseDisplayTitle();
    if (hasData && useCaseTitle !== "My Data") {
      return useCaseTitle;
    }

    if (dataSources.length > 0) {
      return getUseCaseDisplayTitle();
    }

    // User uploaded their own files (no seeded scenario active) — show a generic label.
    if (uploadedFileCount > 0) {
      return "Custom Dataset";
    }
    // Fallback to data sources if no uploaded files
    const parts: string[] = [];
    if (totalRecords > 0) parts.push(`${totalRecords.toLocaleString()} records`);
    if (dataSources.length > 0) {
      const names = dataSources.map((ds: any) => {
        // If use_case is set, use that; otherwise fall back to display_name or name
        if (ds.use_case) return ds.use_case;
        return ds.display_name || ds.name || "External Data";
      });
      parts.push(names.join(" + "));
    }
    return parts.join(" \u00b7 ");
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files: File[] = Array.from(fileList);
    const jsonFiles = files.filter((f) => f.name.toLowerCase().endsWith(".json"));
    const docFiles = files.filter((f) => !f.name.toLowerCase().endsWith(".json"));
    const label = files.length === 1 ? files[0].name : `${files.length} files`;
    setUploading(true);
    setUploadDone(false);
    setUploadError("");
    setUploadMsg(`Uploading ${label}...`);
    try {
      let totalLoaded = 0;
      let docSubmitted = false;
      let docUploadRes: any = null;
      const failures: string[] = [];

      for (const file of jsonFiles) {
        try {
          const res = await uploadJsonFile(file);
          totalLoaded += Number(res?.data?.total_loaded || 0);
        } catch (err) {
          failures.push(`${file.name}: ${getApiErrorMessage(err, "JSON upload failed")}`);
        }
      }

      if (docFiles.length > 0) {
        try {
          docUploadRes = await uploadDocument(docFiles);
          docSubmitted = true;
        } catch (err) {
          failures.push(`Documents: ${getApiErrorMessage(err, "Document upload failed")}`);
        }
      }

      if (jsonFiles.length > 0 && docFiles.length > 0) {
        setUploadMsg(`${totalLoaded} records loaded and ${docFiles.length} document(s) submitted — processing in background`);
      } else if (jsonFiles.length > 0) {
        setUploadMsg(`${totalLoaded} records loaded`);
      } else {
        const queued: number = docUploadRes?.data?.total_loaded ?? docFiles.length;
        const skipped: number = docUploadRes?.data?.skipped ?? 0;
        if (skipped > 0 && queued === 0) {
          setUploadMsg(`${skipped} file(s) already processed — no changes needed`);
        } else if (skipped > 0) {
          setUploadMsg(`${queued} new file(s) queued for processing, ${skipped} already ready`);
        } else {
          setUploadMsg(`${queued} file(s) submitted — processing in background`);
        }
      }

      if (failures.length > 0) {
        setUploadError(`Some uploads failed: ${failures.slice(0, 2).join(" | ")}`);
      }

      if (totalLoaded > 0 || docSubmitted) {
        setUploadDone(true);
      }
      setInsights(null); // Invalidate insights cache so it regenerates with new data
      loadStatus();
    } catch (err: unknown) {
      setUploadError(getApiErrorMessage(err, "Upload failed"));
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
            Upload supported files to enrich your knowledge base.
          </div>
        </div>

        {/* Active Dataset card */}
        <div className={s.sourceCard}>
          {loadingSources ? (
            <Spinner size="small" />
          ) : hasData ? (
            <>
              <div style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap", justifyContent: "center" }}>
                  <Text weight="bold" size={500} style={{ color: "#0f172a", flex: 1 }}>
                    {buildSummary()}
                  </Text>
                  {readyCount > 0 && (
                    <div style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      backgroundColor: "#d1fae5",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 12,
                      color: "#059669",
                      fontWeight: 500
                    }}>
                      ✓ {readyCount} processed
                    </div>
                  )}
                  {chatReadyCount > 0 && (
                    <div style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      backgroundColor: "#dbeafe",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 12,
                      color: "#2563eb",
                      fontWeight: 500
                    }}>
                      💬 {chatReadyCount} chat ready
                    </div>
                  )}
                  {processingCount > 0 && (
                    <div style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      backgroundColor: "#fef3c7",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 12,
                      color: "#d97706",
                      fontWeight: 500
                    }}>
                      ⏳ {processingCount} processing
                    </div>
                  )}
                  {!isExternalConnectionCard && (
                    <div style={{ 
                      display: "inline-flex", 
                      alignItems: "center", 
                      gap: 6,
                      backgroundColor: "#f1f5f9",
                      padding: "4px 10px",
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 500,
                      color: "#475569"
                    }}>
                      📎 {uploadedFiles.length} {uploadedFiles.length === 1 ? "file" : "files"}
                    </div>
                  )}
                </div>
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                <span title={insightsAvailable ? "" : "Insights are still being generated. Chat is available now."}>
                  <Button appearance="primary" size="medium" icon={<ChartMultiple24Regular />}
                    disabled={!insightsAvailable}
                    onClick={() => navigate(primaryExternalSourceName ? `/insights?source=${encodeURIComponent(primaryExternalSourceName)}` : "/insights")}>View insights</Button>
                </span>
                <Button appearance="outline" size="medium" icon={<Search24Regular />}
                  onClick={() => navigate(primaryExternalSourceName ? `/explore?source=${encodeURIComponent(primaryExternalSourceName)}` : "/explore")}>Explore data</Button>
                {!isExternalConnectionCard && dataSources.length === 0 && (
                  <Button appearance="outline" size="medium" icon={<ArrowUpload24Regular />}
                    disabled={uploading}
                    onClick={() => { resetUpload(); fileInputRef.current?.click(); }}>
                    {uploading ? "Uploading…" : "Upload more"}
                  </Button>
                )}
              </div>
              {/* Upload feedback shown inline when data is already present */}
              {!isExternalConnectionCard && dataSources.length === 0 && (uploadMsg || uploadError) && !uploading && (
                <div style={{ marginTop: 8, fontSize: 13 }}>
                  {uploadDone && <span style={{ color: "#059669" }}>✓ {uploadMsg}</span>}
                  {uploadError && <span style={{ color: "#dc2626" }}>⚠ {uploadError}</span>}
                </div>
              )}
            </>
          ) : (
            <>
              <Database24Regular style={{ color: "#94a3b8", fontSize: 24 }} />
              <Text weight="semibold" size={400} style={{ color: "#64748b" }}>
                No data loaded yet
              </Text>
              <Text size={200} style={{ color: "#94a3b8" }}>
                Choose how you'd like to connect your data to get started.
              </Text>
            </>
          )}
        </div>

        {!hasData && (
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
            style={{
              ...(dragOver ? { borderColor: "#2563eb", boxShadow: "0 0 0 4px rgba(37,99,235,0.1)" } : {}),
              ...(uploadDone ? { borderStyle: "solid", borderColor: "#bbf7d0" } : {}),
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
                <Text size={200} style={{ color: "#2563eb", cursor: "pointer", marginTop: 4 }}
                  onClick={(e) => { e.stopPropagation(); resetUpload(); fileInputRef.current?.click(); }}>
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
                  Upload supported files
                </Text>
                <Text size={200} style={{ color: "#94a3b8" }}>Drag & drop or click to browse</Text>
                <div className={s.fileTypes}>
                  {FILE_TYPES.map((ft) => <span key={ft} className={s.fileType}>{ft}</span>)}
                </div>
              </>
            )}

          </div>
        )}

        <input ref={fileInputRef} type="file" multiple style={{ display: "none" }}
          accept={SUPPORTED_UPLOAD_ACCEPT} onChange={handleUpload} />
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
                <div className={s.valueDesc}>Supported formats: {SUPPORTED_UPLOAD_DESCRIPTION}. Files are processed automatically.</div>
              </div>
              <div className={s.valueCard} style={{ cursor: "pointer" }} onClick={() => navigate("/data-sources")}>
                <div className={s.valueIcon} style={{ backgroundColor: "#fef3c7" }}>
                  <Database24Regular style={{ color: "#d97706" }} />
                </div>
                <div className={s.valueTitle}>Connect external data</div>
                <div className={s.valueDesc}>Link Azure AI Search, SQL, Fabric, Synapse, or other data sources to start analyzing immediately.</div>
              </div>
              <div className={s.valueCard}>
                <div className={s.valueIcon} style={{ backgroundColor: "#d1fae5" }}>
                  <TextBulletListSquare20Regular style={{ color: "#059669" }} />
                </div>
                <div className={s.valueTitle}>Load a scenario pack</div>
                <div className={s.valueDesc}>Run <code style={{ fontSize: 11 }}>./infra/scripts/post-provision/setup-data.ps1</code> to load a built-in scenario pack.</div>
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
