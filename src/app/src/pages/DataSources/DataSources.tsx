import React, { useEffect, useState, useCallback } from "react";
import { Button, Badge, Spinner, Text } from "@fluentui/react-components";
import {
  Database24Regular,
  Delete20Regular,
  ArrowSync20Regular,
  DocumentText20Regular,
  Search20Regular,
  DataBarVertical20Regular,
} from "@fluentui/react-icons";
import {
  listDataSources,
  deleteDataSource,
  ingestDataSource,
  getUploadedFiles,
  deleteFile,
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

  const totalFiles = uploadedFiles.length;
  const totalSources = sources.length;
  const totalRecords = uploadedFiles.reduce((sum, f) => sum + (f.doc_count || 0), 0)
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
      {/* Header */}
      <div className="sourcesHeader">
        <h1>Sources</h1>
        <p>Your uploaded files and connected databases</p>
      </div>

      {/* Stats bar */}
      {(totalFiles > 0 || totalSources > 0) && (
        <div className="statsBar">
          <div className="statItem">
            <span className="statValue">{totalFiles}</span>
            <span className="statLabel">{totalFiles === 1 ? "File" : "Files"}</span>
          </div>
          {totalSources > 0 && (
            <div className="statItem">
              <span className="statValue">{totalSources}</span>
              <span className="statLabel">{totalSources === 1 ? "Database" : "Databases"}</span>
            </div>
          )}
          <div className="statItem">
            <span className="statValue">{totalRecords.toLocaleString()}</span>
            <span className="statLabel">Total Records</span>
          </div>
          <div style={{ flex: 1 }} />
          <Button appearance="primary" size="small" icon={<Search20Regular />}
            onClick={() => navigate("/explore")}>Explore All</Button>
          <Button appearance="outline" size="small" icon={<DataBarVertical20Regular />}
            onClick={() => navigate("/insights")}>View Insights</Button>
        </div>
      )}

      {/* File list */}
      {(totalFiles > 0 || totalSources > 0) && (
        <div className="sourcesList">
          {uploadedFiles.map((f) => (
            <div key={`file-${f.id}`} className="sourceRow">
              <div className="sourceIcon fileIcon">
                <DocumentText20Regular />
              </div>
              <div className="sourceInfo">
                <div className="sourceName">{f.filename}</div>
                <div className="sourceMeta">{f.doc_count} {f.doc_count === 1 ? "record" : "records"}</div>
              </div>
              <div className="sourceActions">
                <button className="actionBtn" title="Explore" onClick={() => navigate("/explore")}>
                  <Search20Regular />
                </button>
                <button className="actionBtn" title="Insights" onClick={() => navigate("/insights")}>
                  <DataBarVertical20Regular />
                </button>
                <button className="actionBtn deleteBtn" title="Delete"
                  onClick={() => handleDeleteFile(f.id, f.filename)}>
                  <Delete20Regular />
                </button>
              </div>
            </div>
          ))}
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
                <button className="actionBtn" title="Insights" onClick={() => navigate("/insights")}>
                  <DataBarVertical20Regular />
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
          <Database24Regular style={{ fontSize: 48, color: "#cbd5e1" }} />
          <h3>No data yet</h3>
          <p>Upload files on the Home page to get started.<br />Databases can be connected via environment configuration.</p>
          <Button appearance="primary" onClick={() => navigate("/")}>Go to Home</Button>
        </div>
      )}
    </div>
  );
};

export default DataSources;
