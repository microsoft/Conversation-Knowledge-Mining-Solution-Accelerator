import React, { useState, useRef, useEffect } from "react";
import {
  Text,
  Button,
  Spinner,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
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
  Delete20Regular,
} from "@fluentui/react-icons";
import { useNavigate } from "react-router-dom";
import {
  uploadJsonFile,
  uploadDocument,
  listDataSources,
  getUploadedFiles,
  deleteFile,
  refreshIngestionCache,
} from "../api/client";
import { getApiErrorMessage } from "../utils/errors";
import { FILE_TYPES, SUPPORTED_UPLOAD_ACCEPT, SUPPORTED_UPLOAD_DESCRIPTION } from "../utils/constants";
import { useAppState } from "../context/AppStateContext";
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
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string; count: number } | null>(null);
  const [deleting, setDeleting] = useState(false);
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
  const readyCount = uploadedFiles.filter((f: any) => f.status === "ready" || !f.status).length;
  const chatReadyCount = uploadedFiles.filter((f: any) => f.status === "extracted").length;
  const processingCount = uploadedFiles.filter((f: any) => f.status === "processing").length;
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

  const handleDeleteFile = (id: string, name: string, count: number) => {
    setDeleteTarget({ id, name, count });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteFile(deleteTarget.id);
      setExploreData(null);
      setInsights(null);
      loadStatus();
    } catch (e) {
      setUploadError(`Failed to delete: ${getApiErrorMessage(e, "Unknown error")}`);
    } finally {
      setDeleting(false);
      setDeleteTarget(null);
    }
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
                      <span className={s.fileStatusBadge} style={getFileStatusStyle(f.status)}
                        title={
                          f.status === "extracted"
                            ? "You can ask questions about this document now. Insights and indexing are still processing."
                            : f.status === "failed"
                              ? f.error || "Processing failed"
                              : undefined
                        }>
                        {getFileStatusLabel(f.status)}
                      </span>
                      <button
                        className={s.fileDeleteBtn}
                        title="Delete"
                        onClick={(e) => { e.stopPropagation(); handleDeleteFile(f.id, f.filename, f.doc_count || 0); }}
                      >
                        <Delete20Regular />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {uploadedFiles.length > 0 && (
                <Text size={200} style={{ color: "#64748b", marginTop: 6 }}>
                  {chatReadyCount > 0 ? `${chatReadyCount} ${chatReadyCount === 1 ? "document" : "documents"} ready for chat` : ""}
                  {chatReadyCount > 0 && (readyCount > 0 || processingCount > 0) ? ", " : ""}
                  {readyCount > 0 ? `${readyCount} fully processed` : ""}
                  {processingCount > 0 && (chatReadyCount > 0 || readyCount > 0) ? ", " : ""}
                  {processingCount > 0 ? `${processingCount} still processing` : ""}
                </Text>
              )}
              <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
                <Button appearance="subtle" size="medium" icon={<ArrowUpload24Regular />}
                  onClick={() => fileInputRef.current?.click()}>Upload files</Button>
                <span title={insightsAvailable ? "" : "Insights are still being generated. Chat is available now."}>
                  <Button appearance="primary" size="medium" icon={<ChartMultiple24Regular />}
                    disabled={!insightsAvailable}
                    onClick={() => navigate("/insights")}>View insights</Button>
                </span>
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
                Use the upload box below to get started, or run a scenario pack from the command line.
              </Text>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                <Spinner size="tiny" />
                <Text size={200} style={{ color: "#64748b" }}>
                  Waiting for incoming scenario data. This page refreshes automatically.
                </Text>
              </div>
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

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(_, d) => { if (!d.open) setDeleteTarget(null); }}>
        <DialogSurface style={{ maxWidth: 360, borderRadius: 12, padding: "20px 24px" }}>
          <DialogBody style={{ padding: 0 }}>
            <DialogTitle style={{ padding: 0, margin: "0 0 8px", fontSize: 16 }}>Remove file?</DialogTitle>
            <DialogContent style={{ padding: 0 }}>
              <p style={{ margin: 0, color: "#64748b", fontSize: 13, lineHeight: 1.5 }}>
                <strong style={{ color: "#1e293b" }}>{deleteTarget?.name}</strong>
                {deleteTarget && deleteTarget.count > 0 && (
                  <> and its {deleteTarget.count.toLocaleString()} {deleteTarget.count === 1 ? "record" : "records"}</>
                )} will be permanently removed.
              </p>
            </DialogContent>
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 16 }}>
              <Button appearance="subtle" size="medium" onClick={() => setDeleteTarget(null)} disabled={deleting}>Cancel</Button>
              <Button appearance="primary" size="medium" onClick={confirmDelete} disabled={deleting}
                style={{ backgroundColor: "#dc2626", borderColor: "#dc2626" }}>
                {deleting ? <Spinner size="tiny" /> : "Remove"}
              </Button>
            </div>
          </DialogBody>
        </DialogSurface>
      </Dialog>

    </div>
  );
};

export default Home;
