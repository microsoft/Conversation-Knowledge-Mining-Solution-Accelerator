import React, { useEffect, useState, useCallback } from "react";
import { Button, Badge, Spinner, Text } from "@fluentui/react-components";
import {
  Database24Regular,
  Delete24Regular,
  ArrowSync24Regular,
  DocumentText20Regular,
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

const STATUS_COLORS: Record<string, "success" | "danger" | "warning" | "informative"> = {
  connected: "success",
  disconnected: "warning",
  error: "danger",
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

  if (loading) {
    return (
      <div className="dataSources" style={{ display: "flex", justifyContent: "center", paddingTop: 100 }}>
        <Spinner label="Loading..." />
      </div>
    );
  }

  return (
    <div className="dataSources">
      <div className="header">
        <div className="headerLeft">
          <h1>Sources</h1>
          <p>Your uploaded files and connected databases</p>
        </div>
      </div>

      {(uploadedFiles.length > 0 || sources.length > 0) && (
        <div className="filesList">
          {uploadedFiles.map((f) => (
            <div key={`file-${f.id}`} className="fileRow">
              <DocumentText20Regular style={{ color: "#64748b", flexShrink: 0 }} />
              <div className="fileRowName">{f.filename}</div>
              <div className="fileRowMeta">{f.doc_count} records</div>
              <div className="fileRowActions">
                <Button appearance="subtle" size="small" onClick={() => navigate("/explore")}>Explore</Button>
                <Button appearance="subtle" size="small" onClick={() => navigate("/insights")}>Insights</Button>
                <button className="fileDeleteBtn" title="Delete"
                  onClick={() => handleDeleteFile(f.id, f.filename)}>
                  <Delete24Regular />
                </button>
              </div>
            </div>
          ))}
          {sources.map((src) => (
            <div key={`ds-${src.id}`} className="fileRow">
              <Database24Regular style={{ color: "#2563eb", flexShrink: 0, fontSize: 20 }} />
              <div className="fileRowName">
                {src.name}
                <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 8 }}>
                  {TYPE_LABELS[src.source_type] || src.source_type}
                </span>
              </div>
              <Badge appearance="filled" color={STATUS_COLORS[src.status] || "informative"} size="small" style={{ flexShrink: 0 }}>
                {src.status}
              </Badge>
              <div className="fileRowMeta">{src.doc_count.toLocaleString()} rows</div>
              <div className="fileRowActions">
                <Button appearance="subtle" size="small" onClick={() => navigate("/explore")}>Explore</Button>
                <Button appearance="subtle" size="small" onClick={() => navigate("/insights")}>Insights</Button>
                {(src.query_mode === "ingest" || src.query_mode === "both") && (
                  <Button size="small" appearance="subtle"
                    icon={ingesting === src.id ? <Spinner size="tiny" /> : <ArrowSync24Regular />}
                    onClick={() => handleIngest(src.id)} disabled={ingesting === src.id}>
                    {ingesting === src.id ? "Syncing..." : "Sync"}
                  </Button>
                )}
                <button className="fileDeleteBtn" title="Delete"
                  onClick={() => handleDeleteSource(src.id)}>
                  <Delete24Regular />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {sources.length === 0 && uploadedFiles.length === 0 && (
        <div className="emptyState">
          <Database24Regular style={{ fontSize: 40, color: "#94a3b8" }} />
          <h3>No data yet</h3>
          <p>Upload files on the Home page to get started. Databases can be connected via environment configuration.</p>
        </div>
      )}
    </div>
  );
};

export default DataSources;
