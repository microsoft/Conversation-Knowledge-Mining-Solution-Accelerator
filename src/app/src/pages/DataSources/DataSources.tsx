import React, { useEffect, useState, useCallback, useRef } from "react";
import { Button, Badge, Spinner, Text, ProgressBar } from "@fluentui/react-components";
import {
  Database24Regular,
  Delete20Regular,
  ArrowSync20Regular,
  DocumentText20Regular,
  Search20Regular,
  DataBarVertical20Regular,
  ArrowUpload20Regular,
  CheckmarkCircle20Regular,
  ErrorCircle20Regular,
} from "@fluentui/react-icons";
import {
  listDataSources,
  deleteDataSource,
  ingestDataSource,
  getUploadedFiles,
  deleteFile,
  uploadDocument,
} from "../../api/client";
import { useNavigate } from "react-router-dom";
import "./DataSources.css";

const TYPE_LABELS: Record<string, string> = {
  fabric: "Microsoft Fabric",
  sql: "SQL Database",
  synapse: "Azure Synapse",
  odbc: "ODBC / JDBC",
  azure_search: "Azure AI Search",
};

const DataSources: React.FC = () => {
  const navigate = useNavigate();
  const [sources, setSources] = useState<any[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadSources = useCallback(async () => {
    try {
      const [srcRes, filesRes] = await Promise.allSettled([
        listDataSources(),
        getUploadedFiles(),
      ]);
      setSources(srcRes.status === "fulfilled" ? srcRes.value.data : []);
      setUploadedFiles(filesRes.status === "fulfilled" ? filesRes.value.data : []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  // Auto-refresh while any file is still processing
  useEffect(() => {
    const hasProcessing = uploadedFiles.some((f) => f.status === "processing");
    if (!hasProcessing) return;
    const interval = setInterval(() => { loadSources(); }, 5000);
    return () => clearInterval(interval);
  }, [uploadedFiles, loadSources]);

  const handleDeleteFile = async (id: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"?`)) return;
    try { await deleteFile(id); loadSources(); } catch { /* ignore */ }
  };

  const handleDeleteSource = async (id: string) => {
    try { await deleteDataSource(id); loadSources(); } catch { /* ignore */ }
  };

  const handleIngest = async (id: string) => {
    setIngesting(id);
    try { await ingestDataSource(id); loadSources(); } catch { /* ignore */ }
    finally { setIngesting(null); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;
    try {
      await uploadDocument(Array.from(fileList));
      loadSources();
    } catch { /* ignore */ }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const totalFiles = uploadedFiles.length;
  const totalSources = sources.length;
  const readyFiles = uploadedFiles.filter((f) => f.status === "ready");
  const processingFiles = uploadedFiles.filter((f) => f.status === "processing");
  const failedFiles = uploadedFiles.filter((f) => f.status === "failed");
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
      {/* Header with upload button */}
      <div className="sourcesHeader">
        <div>
          <h1>Sources</h1>
          <p>Your uploaded files and connected databases</p>
        </div>
        <div className="sourcesHeaderActions">
          <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.csv,.json"
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
            onClick={() => navigate("/explore")} disabled={readyFiles.length === 0}>Explore</Button>
          <Button appearance="outline" size="small" icon={<DataBarVertical20Regular />}
            onClick={() => navigate("/insights")} disabled={readyFiles.length === 0}>Insights</Button>
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
            <div key={`ds-${src.id}`} className="sourceRow">
              <div className="sourceIcon dbIcon">
                <Database24Regular style={{ fontSize: 18 }} />
              </div>
              <div className="sourceInfo">
                <div className="sourceName">
                  {src.name}
                  <Badge appearance="tint" size="small" color={src.status === "connected" ? "success" : src.status === "error" ? "danger" : "warning"}
                    style={{ marginLeft: 8, verticalAlign: "middle" }}>
                    {src.status}
                  </Badge>
                </div>
                <div className="sourceMeta">
                  {TYPE_LABELS[src.source_type] || src.source_type} · {src.doc_count.toLocaleString()} rows
                </div>
              </div>
              <div className="sourceActions">
                {(src.query_mode === "ingest" || src.query_mode === "both") && (
                  <button className="actionBtn" title="Sync"
                    onClick={() => handleIngest(src.id)} disabled={ingesting === src.id}>
                    {ingesting === src.id ? <Spinner size="tiny" /> : <ArrowSync20Regular />}
                  </button>
                )}
                <button className="actionBtn" title="Explore" onClick={() => navigate("/explore")}>
                  <Search20Regular />
                </button>
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
          <p>Upload files to get started. Supported formats: PDF, DOCX, images, text, CSV, and JSON.</p>
          <Button appearance="primary" icon={<ArrowUpload20Regular />}
            onClick={() => fileInputRef.current?.click()}>Upload files</Button>
        </div>
      )}
    </div>
  );
};

export default DataSources;
