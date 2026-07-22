import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Button,
  Badge,
  Spinner,
  Text,
  ProgressBar,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
} from "@fluentui/react-components";
import {
  Database24Regular,
  Delete20Regular,
  ArrowSync20Regular,
  DocumentText20Regular,
  Search20Regular,
  DataBarVertical20Regular,
  ArrowUpload20Regular,
  ErrorCircle20Regular,
} from "@fluentui/react-icons";
import {
  listDataSources,
  deleteDataSource,
  ingestDataSource,
  getUploadedFiles,
  deleteFile,
  retryFile,
  uploadJsonFile,
  uploadDocument,
} from "../../api/client";
import type { UploadedFile, DataSourceConfig } from "../../types/api";
import { useNavigate } from "react-router-dom";
import { useAppState } from "../../context/AppStateContext";
import { getApiErrorMessage } from "../../utils/errors";
import { SUPPORTED_UPLOAD_ACCEPT, SUPPORTED_UPLOAD_DESCRIPTION } from "../../utils/constants";
import "./DataSources.css";

const TYPE_LABELS: Record<string, string> = {
  fabric: "Microsoft Fabric",
  sql: "SQL Database",
  synapse: "Azure Synapse",
  odbc: "ODBC / JDBC",
  azure_search: "Azure AI Search",
};

const formatSourceDocumentLabel = (sourceType: string, count: number) => {
  if (sourceType === "azure_search") {
    return `${count.toLocaleString()} indexed item${count === 1 ? "" : "s"}`;
  }
  return `${count.toLocaleString()} ${count === 1 ? "record" : "records"}`;
};

const formatSourceStatus = (status: string) => {
  if (status === "connected") return "Connected";
  if (status === "error") return "Connection error";
  return status;
};

const DataSources: React.FC = () => {
  const navigate = useNavigate();
  const { setExploreData, setInsights, ingestionSnapshot } = useAppState();
  const [sources, setSources] = useState<DataSourceConfig[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadedFilesRef = useRef<UploadedFile[]>([]);
  const sourcesRef = useRef<DataSourceConfig[]>([]);

  useEffect(() => {
    uploadedFilesRef.current = uploadedFiles;
  }, [uploadedFiles]);

  useEffect(() => {
    sourcesRef.current = sources;
  }, [sources]);

  const loadSources = useCallback(async () => {
    try {
      // During processing, only fetch files; skip data-sources to reduce traffic
      const hasProcessing = uploadedFilesRef.current.some((f) => f.status === "processing");
      const requests: any[] = [getUploadedFiles()];
      if (!hasProcessing) requests.push(listDataSources());
      else requests.push(Promise.resolve({ data: sourcesRef.current }) as any);
      
      const [filesRes, srcRes] = await Promise.allSettled(requests);
      setUploadedFiles(filesRes.status === "fulfilled" && Array.isArray(filesRes.value.data) ? filesRes.value.data : []);
      const rawSrc = srcRes.status === "fulfilled" && Array.isArray(srcRes.value.data) ? srcRes.value.data : sourcesRef.current;
      // Hide inert 'native' scenario markers — they exist only to surface the
      // use-case name on Home, not as real connections.
      setSources(rawSrc.filter((s: any) => s.source_type !== "native"));
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  // Shared app-level polling updates this page through ingestionSnapshot.
  useEffect(() => {
    if (!ingestionSnapshot) return;
    setUploadedFiles(Array.isArray(ingestionSnapshot.uploadedFiles) ? ingestionSnapshot.uploadedFiles : []);
    setSources(
      Array.isArray(ingestionSnapshot.dataSources)
        ? ingestionSnapshot.dataSources.filter((s: any) => s.source_type !== "native")
        : []
    );
  }, [ingestionSnapshot]);

  const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
  const [deleting, setDeleting] = useState(false);

  const handleDeleteFile = async (id: string, filename: string) => {
    setDeleteTarget({ id, name: filename });
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try { await deleteFile(deleteTarget.id); setExploreData(null); setInsights(null); loadSources(); } catch (e) { setError(`Failed to delete file: ${getApiErrorMessage(e, "Unknown error")}`); }
    finally { setDeleting(false); setDeleteTarget(null); }
  };

  const handleDeleteSource = async (id: string) => {
    try { await deleteDataSource(id); loadSources(); } catch (e) { setError(`Failed to delete data source: ${getApiErrorMessage(e, "Unknown error")}`); }
  };

  const handleRetry = async (id: string) => {
    try { await retryFile(id); setExploreData(null); loadSources(); } catch (e) { setError(`Retry failed: ${getApiErrorMessage(e, "Unknown error")}`); }
  };

  const handleIngest = async (id: string) => {
    setIngesting(id);
    try { await ingestDataSource(id); loadSources(); } catch (e) { setError(`Ingestion failed: ${getApiErrorMessage(e, "Unknown error")}`); }
    finally { setIngesting(null); }
  };

  const MAX_FILE_SIZE_MB = 100;

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    const files: File[] = Array.from(fileList);
    const jsonFiles = files.filter((f) => f.name.toLowerCase().endsWith(".json"));
    const docFiles = files.filter((f) => !f.name.toLowerCase().endsWith(".json"));
    const oversized = files.filter((f) => f.size > MAX_FILE_SIZE_MB * 1024 * 1024);
    if (oversized.length > 0) {
      setError(`${oversized.map((f) => f.name).join(", ")} exceeded the ${MAX_FILE_SIZE_MB} MB limit.`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    try {
      const failures: string[] = [];
      let docsSubmitted = false;

      for (const file of jsonFiles) {
        try {
          await uploadJsonFile(file);
        } catch (err) {
          failures.push(`${file.name}: ${getApiErrorMessage(err, "JSON upload failed")}`);
        }
      }
      if (docFiles.length > 0) {
        try {
          await uploadDocument(docFiles);
          docsSubmitted = true;
        } catch (err) {
          failures.push(`Documents: ${getApiErrorMessage(err, "Document upload failed")}`);
        }
      }

      if (failures.length > 0) {
        setError(`Some uploads failed: ${failures.slice(0, 2).join(" | ")}`);
      }

      if (jsonFiles.length > 0 || docsSubmitted) {
        setInsights(null);
        setExploreData(null);
        loadSources();
      }
    } catch (e) { setError(`Upload failed: ${getApiErrorMessage(e, "Unknown error")}`); }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const totalFiles = uploadedFiles.length;
  const totalSources = sources.length;
  const readyFiles = uploadedFiles.filter((f) => f.status === "ready");
  const processingFiles = uploadedFiles.filter((f) => f.status === "processing");
  const failedFiles = uploadedFiles.filter((f) => f.status === "failed");
  const connectedSources = sources.filter((s) => s.status === "connected");
  const hasKnowledgeSources = readyFiles.length > 0 || connectedSources.length > 0;
  const totalRecords = readyFiles.reduce((sum, f) => sum + (f.doc_count || 0), 0)
    + sources.reduce((sum, s) => sum + (s.doc_count || 0), 0);

  if (loading) {
    return (
      <div className="sourcesPage" style={{ display: "flex", justifyContent: "center", paddingTop: 100 }}>
        <Spinner label="Loading..." />
      </div>
    );
  }

  return (
    <div className="sourcesPage">
      {/* Error banner */}
      {error && (
        <div style={{ padding: "10px 16px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: 8, color: "#991b1b", fontSize: 13, display: "flex", alignItems: "center", gap: 8, margin: "0 0 12px" }}>
          <ErrorCircle20Regular />
          <span style={{ flex: 1 }}>{error}</span>
          <button onClick={() => setError(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "#991b1b", fontWeight: 600 }}>Dismiss</button>
        </div>
      )}
      {/* Header with upload button */}
      <div className="sourcesHeader">
        <div>
          <h1>Sources</h1>
          <p>Your uploaded files</p>
        </div>
        <div className="sourcesHeaderActions">
          <input ref={fileInputRef} type="file" multiple accept={SUPPORTED_UPLOAD_ACCEPT}
            style={{ display: "none" }} onChange={handleUpload} />
          <Button appearance="primary" size="small" icon={<ArrowUpload20Regular />}
            onClick={() => fileInputRef.current?.click()}>Upload files</Button>
        </div>
      </div>

      {/* Processing banner */}
      {processingFiles.length > 0 && (
        <div className="processingBanner">
          <div className="processingBannerContent">
            <Spinner size="tiny" />
            <span>
              Processing {processingFiles.length} {processingFiles.length === 1 ? "file" : "files"}...
            </span>
          </div>
          <ProgressBar thickness="medium" />
        </div>
      )}

      {/* Stats bar */}
      {(totalFiles > 0 || totalSources > 0) && (
        <div className="statsBar">
          <div className="statItem">
            <span className="statValue">{readyFiles.length}</span>
            <span className="statLabel">Ready</span>
          </div>
          {processingFiles.length > 0 && (
            <div className="statItem">
              <span className="statValue statProcessing">{processingFiles.length}</span>
              <span className="statLabel">Processing</span>
            </div>
          )}
          {failedFiles.length > 0 && (
            <div className="statItem">
              <span className="statValue statFailed">{failedFiles.length}</span>
              <span className="statLabel">Failed</span>
            </div>
          )}
          {totalSources > 0 && (
            <div className="statItem">
              <span className="statValue">{totalSources}</span>
              <span className="statLabel">{totalSources === 1 ? "Database" : "Databases"}</span>
            </div>
          )}
          <div className="statItem">
            <span className="statValue">{totalRecords.toLocaleString()}</span>
            <span className="statLabel">Records</span>
          </div>
          <div style={{ flex: 1 }} />
          <Button appearance="primary" size="small" icon={<Search20Regular />}
            onClick={() => navigate("/explore")} disabled={!hasKnowledgeSources}>Explore</Button>
          <Button appearance="outline" size="small" icon={<DataBarVertical20Regular />}
            onClick={() => navigate("/insights")} disabled={!hasKnowledgeSources}>Insights</Button>
        </div>
      )}

      {/* File list — processing files first */}
      {(totalFiles > 0 || totalSources > 0) && (
        <div className="sourcesList">
          {/* Processing files */}
          {processingFiles.map((f) => (
            <div key={`file-${f.id}`} className="sourceRow sourceRowProcessing">
              <div className="sourceIcon fileIconProcessing">
                <Spinner size="tiny" />
              </div>
              <div className="sourceInfo">
                <div className="sourceName">{f.filename}</div>
                <div className="sourceMeta">Extracting and indexing content...</div>
              </div>
            </div>
          ))}

          {/* Failed files */}
          {failedFiles.map((f) => (
            <div key={`file-${f.id}`} className="sourceRow sourceRowFailed">
              <div className="sourceIcon fileIconFailed">
                <ErrorCircle20Regular />
              </div>
              <div className="sourceInfo">
                <div className="sourceName">{f.filename}</div>
                <div className="sourceMetaError">{f.error || "Processing failed"}</div>
              </div>
              <div className="sourceActions sourceActionsVisible">
                <button className="actionBtn" title="Retry"
                  onClick={() => handleRetry(f.id)}>
                  <ArrowSync20Regular />
                </button>
                <button className="actionBtn deleteBtn" title="Delete"
                  onClick={() => handleDeleteFile(f.id, f.filename)}>
                  <Delete20Regular />
                </button>
              </div>
            </div>
          ))}

          {/* Ready files */}
          {readyFiles.map((f) => (
            <div key={`file-${f.id}`} className="sourceRow">
              <div className="sourceIcon fileIcon">
                <DocumentText20Regular />
              </div>
              <div className="sourceInfo">
                <div className="sourceName">{f.filename}</div>
                <div className="sourceMeta">{f.doc_count} {f.doc_count === 1 ? "record" : "records"}{f.summary && f.summary !== "Processing..." ? ` · ${f.summary}` : ""}</div>
              </div>
              <div className="sourceActions">
                <button className="actionBtn" title="Explore" onClick={() => navigate("/explore")}>
                  <Search20Regular />
                </button>
                <button className="actionBtn deleteBtn" title="Delete"
                  onClick={() => handleDeleteFile(f.id, f.filename)}>
                  <Delete20Regular />
                </button>
              </div>
            </div>
          ))}

          {/* Database sources */}
          {sources.map((src) => (
            <div key={`ds-${src.id}`} className="sourceRow sourceRowCard">
              <div className="sourceCardHeader">
                <div className="sourceIcon dbIcon">
                  <Database24Regular style={{ fontSize: 18 }} />
                </div>
                <div className="sourceCardTitle">Knowledge Source</div>
              </div>
              <div className="sourceInfo sourceInfoCard">
                <div className="sourceFieldRow">
                  <span className="sourceFieldLabel">Name:</span>
                  <span className="sourceFieldValue">{src.name}</span>
                </div>
                <div className="sourceFieldRow">
                  <span className="sourceFieldLabel">Type:</span>
                  <span className="sourceFieldValue">{TYPE_LABELS[src.source_type] || src.source_type}</span>
                </div>
                <div className="sourceFieldRow">
                  <span className="sourceFieldLabel">Status:</span>
                  <span className="sourceFieldValue sourceFieldStatus">
                    <Badge appearance="tint" size="small" color={src.status === "connected" ? "success" : src.status === "error" ? "danger" : "warning"}>
                      {src.status === "connected" ? "✓ " : ""}{formatSourceStatus(src.status)}
                    </Badge>
                  </span>
                </div>
                <div className="sourceFieldRow">
                  <span className="sourceFieldLabel">Documents:</span>
                  <span className="sourceFieldValue">{formatSourceDocumentLabel(src.source_type, src.doc_count ?? 0)}</span>
                </div>
              </div>
              <div className="sourceActions sourceActionsVisible sourceActionsCard">
                {(src.query_mode === "ingest" || src.query_mode === "both") && (
                  <button className="actionBtn" title="Sync"
                    onClick={() => handleIngest(src.id)} disabled={ingesting === src.id}>
                    {ingesting === src.id ? <Spinner size="tiny" /> : <ArrowSync20Regular />}
                  </button>
                )}
                <Button appearance="outline" size="small" onClick={() => navigate(`/insights?source=${encodeURIComponent(src.name)}`)}>View Insights</Button>
                <Button appearance="primary" size="small" icon={<Search20Regular />} onClick={() => navigate(`/explore?source=${encodeURIComponent(src.name)}`)}>Explore Data</Button>
                <button className="actionBtn deleteBtn" title="Delete"
                  onClick={() => handleDeleteSource(src.id)}>
                  <Delete20Regular />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Empty state */}
      {totalFiles === 0 && totalSources === 0 && (
        <div className="emptyState">
          <ArrowUpload20Regular style={{ fontSize: 48, color: "#cbd5e1" }} />
          <h3>No data yet</h3>
          <p>Upload files to get started. Supported formats: {SUPPORTED_UPLOAD_DESCRIPTION}.</p>
          <Button appearance="primary" icon={<ArrowUpload20Regular />}
            onClick={() => fileInputRef.current?.click()}>Upload files</Button>
        </div>
      )}
      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(_, d) => { if (!d.open) setDeleteTarget(null); }}>
        <DialogSurface style={{ maxWidth: 420, borderRadius: 16, padding: 0, overflow: "hidden" }}>
          <DialogBody style={{ padding: 0 }}>
            <div style={{ padding: "24px 24px 0", display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 40, height: 40, borderRadius: 10, background: "#fef2f2", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <Delete20Regular style={{ color: "#dc2626" }} />
              </div>
              <DialogTitle style={{ padding: 0, margin: 0 }}>Delete file</DialogTitle>
            </div>
            <DialogContent style={{ padding: "16px 24px 20px" }}>
              <p style={{ margin: "0 0 12px", color: "#374151", fontSize: 14, lineHeight: 1.5 }}>
                Are you sure you want to delete <strong>{deleteTarget?.name}</strong>?
              </p>
              {(() => {
                const target = uploadedFiles.find(f => f.id === deleteTarget?.id);
                const count = target?.doc_count || 0;
                return count > 0 ? (
                  <div style={{ padding: "10px 14px", background: "#fef2f2", borderRadius: 8, fontSize: 13, color: "#991b1b", display: "flex", alignItems: "center", gap: 8 }}>
                    <ErrorCircle20Regular style={{ flexShrink: 0 }} />
                    <span>This will permanently remove <strong>{count.toLocaleString()} {count === 1 ? "record" : "records"}</strong> from insights and search.</span>
                  </div>
                ) : null;
              })()}
            </DialogContent>
            <div style={{ padding: "0 24px 20px", display: "flex", justifyContent: "flex-end", gap: 8 }}>
              <Button appearance="subtle" onClick={() => setDeleteTarget(null)} disabled={deleting}
                style={{ borderRadius: 8 }}>Cancel</Button>
              <Button appearance="primary" onClick={confirmDelete} disabled={deleting}
                style={{ backgroundColor: "#dc2626", borderColor: "#dc2626", borderRadius: 8 }}>
                {deleting ? <Spinner size="tiny" /> : "Delete"}
              </Button>
            </div>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
};

export default DataSources;
