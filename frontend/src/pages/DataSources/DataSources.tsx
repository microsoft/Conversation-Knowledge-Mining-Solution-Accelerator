import React, { useEffect, useState, useCallback } from "react";
import {
  Button,
  Badge,
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Input,
  Dropdown,
  Option,
  Spinner,
  Text,
  Field,
  Textarea,
} from "@fluentui/react-components";
import {
  Add24Regular,
  Database24Regular,
  PlugConnected24Regular,
  Delete24Regular,
  ArrowSync24Regular,
  Checkmark24Regular,
  Dismiss24Regular,
  Settings20Regular,
  ChevronDown20Regular,
  ChevronUp20Regular,
  Eye24Regular,
  DocumentText20Regular,
} from "@fluentui/react-icons";
import {
  listDataSources,
  deleteDataSource,
  testExistingDataSource,
  getDataSourceSample,
  ingestDataSource,
  getDataSourceTypes,
  quickConnectDataSource,
  getUploadedFiles,
  deleteFile,
} from "../../api/client";
import { useNavigate } from "react-router-dom";
import "./DataSources.css";

interface DataSourceInfo {
  id: string;
  name: string;
  source_type: string;
  endpoint: string;
  database: string;
  table_or_query: string;
  auth_method: string;
  field_mapping: {
    id_field: string;
    text_field: string;
    title_field: string;
    type_field: string;
    timestamp_field: string;
    metadata_fields: Record<string, string>;
  };
  query_mode: string;
  status: string;
  doc_count: number;
  last_sync: string;
  error_message: string;
}

interface SourceTypeInfo {
  source_type: string;
  label: string;
  description: string;
  requires_connection_string: boolean;
  requires_endpoint: boolean;
}

interface ColumnInfo {
  name: string;
  data_type: string;
}

const FALLBACK_TYPES: SourceTypeInfo[] = [
  { source_type: "fabric", label: "Microsoft Fabric", description: "Lakehouse or Warehouse via SQL endpoint", requires_connection_string: false, requires_endpoint: true },
  { source_type: "sql", label: "SQL Database", description: "SQL Server, PostgreSQL, MySQL", requires_connection_string: true, requires_endpoint: false },
  { source_type: "synapse", label: "Azure Synapse", description: "Serverless or dedicated SQL pools", requires_connection_string: false, requires_endpoint: true },
  { source_type: "odbc", label: "ODBC / JDBC", description: "Any database with an ODBC driver", requires_connection_string: true, requires_endpoint: false },
  { source_type: "azure_search", label: "Azure AI Search", description: "Existing search index", requires_connection_string: false, requires_endpoint: true },
];

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

/** Auto-detect source type from endpoint/connection string */
function detectSourceType(endpoint: string, connStr: string): string {
  const e = endpoint.toLowerCase();
  const c = connStr.toLowerCase();
  if (e.includes("fabric.microsoft.com") || e.includes("pbidedicated")) return "fabric";
  if (e.includes("sql.azuresynapse.net") || e.includes("synapse")) return "synapse";
  if (e.includes("search.windows.net")) return "azure_search";
  if (c.includes("driver=") || c.includes("dsn=")) return "odbc";
  if (e || c) return "sql";
  return "";
}

const DataSources: React.FC = () => {
  const navigate = useNavigate();
  const [sources, setSources] = useState<DataSourceInfo[]>([]);
  const [sourceTypes, setSourceTypes] = useState<SourceTypeInfo[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ id: string; filename: string; doc_count: number; summary: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [showWizard, setShowWizard] = useState(false);
  const [wizardStep, setWizardStep] = useState(0);
  const [ingesting, setIngesting] = useState<string | null>(null);
  const [previewSourceId, setPreviewSourceId] = useState<string | null>(null);

  // ── Wizard state ──
  const [selectedType, setSelectedType] = useState("");
  const [formName, setFormName] = useState("");
  const [formConnectionString, setFormConnectionString] = useState("");
  const [formEndpoint, setFormEndpoint] = useState("");
  const [formDatabase, setFormDatabase] = useState("");
  const [formTableOrQuery, setFormTableOrQuery] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [connectError, setConnectError] = useState("");

  // Step 1 (preview) state
  const [createdSource, setCreatedSource] = useState<DataSourceInfo | null>(null);
  const [sampleData, setSampleData] = useState<any[]>([]);
  const [columns, setColumns] = useState<ColumnInfo[]>([]);
  const [suggestedMapping, setSuggestedMapping] = useState<any>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [fieldMapping, setFieldMapping] = useState({
    id_field: "id", text_field: "text", title_field: "", type_field: "", timestamp_field: "",
  });

  // Source card preview
  const [cardSampleData, setCardSampleData] = useState<any[]>([]);

  const loadSources = useCallback(async () => {
    try {
      const [srcRes, typesRes, filesRes] = await Promise.allSettled([
        listDataSources(),
        getDataSourceTypes(),
        getUploadedFiles(),
      ]);
      setSources(srcRes.status === "fulfilled" ? srcRes.value.data : []);
      setSourceTypes(typesRes.status === "fulfilled" && typesRes.value.data?.length ? typesRes.value.data : FALLBACK_TYPES);
      setUploadedFiles(filesRes.status === "fulfilled" ? filesRes.value.data : []);
    } catch {
      setSourceTypes(FALLBACK_TYPES);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadSources(); }, [loadSources]);

  const resetWizard = () => {
    setWizardStep(0);
    setSelectedType("");
    setFormName("");
    setFormConnectionString("");
    setFormEndpoint("");
    setFormDatabase("");
    setFormTableOrQuery("");
    setConnecting(false);
    setConnectError("");
    setCreatedSource(null);
    setSampleData([]);
    setColumns([]);
    setSuggestedMapping(null);
    setShowAdvanced(false);
    setFieldMapping({ id_field: "id", text_field: "text", title_field: "", type_field: "", timestamp_field: "" });
  };

  const selectedTypeInfo = sourceTypes.find((t) => t.source_type === selectedType);
  const needsEndpoint = selectedTypeInfo?.requires_endpoint ?? false;
  const needsConnStr = selectedTypeInfo?.requires_connection_string ?? false;

  /** Step 0 → Connect: one-shot test + create + sample */
  const handleConnect = async () => {
    setConnecting(true);
    setConnectError("");
    try {
      const autoName = formName || formTableOrQuery.split(/\s/)[0] || "My Data Source";
      const autoType = selectedType || detectSourceType(formEndpoint, formConnectionString) || "sql";

      const res = await quickConnectDataSource({
        name: autoName,
        source_type: autoType,
        connection_string: formConnectionString,
        endpoint: formEndpoint,
        database: formDatabase,
        table_or_query: formTableOrQuery,
        auth_method: needsEndpoint ? "managed_identity" : "connection_string",
        query_mode: "both",
      });

      if (!res.data.success) {
        setConnectError(res.data.message || "Could not connect. Check your details and try again.");
        return;
      }

      setCreatedSource(res.data.source);
      setSampleData(res.data.sample || []);
      setColumns(res.data.columns || []);
      if (res.data.suggested_mapping) {
        setSuggestedMapping(res.data.suggested_mapping);
        setFieldMapping(res.data.suggested_mapping);
      }
      setWizardStep(1);
      loadSources();
    } catch (e: any) {
      setConnectError(e.response?.data?.detail || e.message || "Connection failed");
    } finally {
      setConnecting(false);
    }
  };

  const canConnect = !!formTableOrQuery && (!!formConnectionString || !!formEndpoint);

  // ── Source card actions ──
  const handleDelete = async (id: string) => {
    try { await deleteDataSource(id); loadSources(); } catch { /* ignore */ }
  };
  const handleIngest = async (id: string) => {
    setIngesting(id);
    try { await ingestDataSource(id); loadSources(); } catch { /* ignore */ }
    finally { setIngesting(null); }
  };
  const handleTestExisting = async (id: string) => {
    try { await testExistingDataSource(id); loadSources(); } catch { /* ignore */ }
  };
  const handleLoadSample = async (sourceId: string) => {
    setPreviewSourceId(previewSourceId === sourceId ? null : sourceId);
    try { setCardSampleData((await getDataSourceSample(sourceId, 5)).data); }
    catch { setCardSampleData([]); }
  };

  if (loading) {
    return (
      <div className="dataSources" style={{ display: "flex", justifyContent: "center", paddingTop: 100 }}>
        <Spinner label="Loading data sources..." />
      </div>
    );
  }

  return (
    <div className="dataSources">
      <div className="header">
        <div className="headerLeft">
          <h1>Sources</h1>
          <p>All your uploaded files and connected databases in one place</p>
        </div>
        <Button appearance="primary" icon={<Add24Regular />}
          onClick={() => { resetWizard(); setShowWizard(true); }}>
          Connect Database
        </Button>
      </div>

      {/* ── Your Data — unified list of files + connected sources ── */}
      {(uploadedFiles.length > 0 || sources.length > 0) && (
        <div style={{ marginBottom: 28 }}>
          <div className="filesList">
            {uploadedFiles.map((f) => (
              <div key={`file-${f.id}`} className="fileRow">
                <DocumentText20Regular style={{ color: "#64748b", flexShrink: 0 }} />
                <div className="fileRowName">{f.filename}</div>
                <div className="fileRowMeta">{f.doc_count} records</div>
                <div className="fileRowActions">
                  <Button appearance="subtle" size="small" onClick={() => navigate("/explore")}>Explore</Button>
                  <Button appearance="subtle" size="small" onClick={() => navigate("/insights")}>Insights</Button>
                  <button className="fileDeleteBtn" title="Delete" onClick={async () => {
                    if (!window.confirm(`Delete "${f.filename}"?`)) return;
                    try { await deleteFile(f.id); loadSources(); } catch { /* ignore */ }
                  }}><Delete24Regular /></button>
                </div>
              </div>
            ))}
            {sources.map((src) => (
              <div key={`ds-${src.id}`} className="fileRow">
                <Database24Regular style={{ color: "#2563eb", flexShrink: 0, fontSize: 20 }} />
                <div className="fileRowName">
                  {src.name}
                  <span style={{ fontSize: 11, color: "#94a3b8", marginLeft: 8 }}>{TYPE_LABELS[src.source_type] || src.source_type}</span>
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
                  <button className="fileDeleteBtn" title="Delete" onClick={() => handleDelete(src.id)}>
                    <Delete24Regular />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Empty state ── */}
      {sources.length === 0 && uploadedFiles.length === 0 && (
        <div className="emptyState">
          <Database24Regular style={{ fontSize: 40, color: "#94a3b8" }} />
          <h3>No data yet</h3>
          <p>Upload files on the Home page or connect a database to get started.</p>
          <Button appearance="primary" icon={<Add24Regular />}
            onClick={() => { resetWizard(); setShowWizard(true); }}>
            Connect Your First Database
          </Button>
        </div>
      )}

      {/* ═══════════ Simplified 3-Step Wizard ═══════════ */}
      <Dialog open={showWizard} onOpenChange={(_, d) => { if (!d.open) { setShowWizard(false); resetWizard(); } }}>
        <DialogSurface style={{ maxWidth: 620 }}>
          <DialogBody>
            <DialogTitle>
              {wizardStep === 0 && "Connect Your Data"}
              {wizardStep === 1 && "Preview & Confirm"}
              {wizardStep === 2 && "You're All Set!"}
            </DialogTitle>

            <DialogContent>
              {/* ── Step 0: Connect ── */}
              {wizardStep === 0 && (
                <div className="wizardStep">
                  <p className="wizardHint">
                    Paste your connection details — we'll auto-detect the source type and map your columns.
                  </p>

                  {/* Source type pills — pick one or let auto-detect handle it */}
                  <div className="typePills">
                    {sourceTypes.map((t) => (
                      <button key={t.source_type}
                        className={selectedType === t.source_type ? "typePillActive" : "typePill"}
                        onClick={() => setSelectedType(t.source_type)}>
                        {t.label}
                      </button>
                    ))}
                  </div>

                  <div className="fieldGroup">
                    {/* Show endpoint field when type needs it OR when no type selected yet */}
                    {(needsEndpoint || !selectedType) && (
                      <Field label="Server / Endpoint">
                        <Input value={formEndpoint}
                          onChange={(_, d) => {
                            setFormEndpoint(d.value);
                            if (!selectedType) setSelectedType(detectSourceType(d.value, formConnectionString));
                          }}
                          placeholder="your-server.database.fabric.microsoft.com" />
                      </Field>
                    )}

                    {/* Show connection string when type needs it OR user hasn't provided an endpoint */}
                    {(needsConnStr || (!selectedType && !formEndpoint)) && (
                      <Field label="Connection String">
                        <Textarea value={formConnectionString}
                          onChange={(_, d) => {
                            setFormConnectionString(d.value);
                            if (!selectedType) setSelectedType(detectSourceType(formEndpoint, d.value));
                          }}
                          placeholder="Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;"
                          rows={2} />
                      </Field>
                    )}

                    {/* Database name for endpoint-based sources */}
                    {(needsEndpoint || (selectedType && !needsConnStr)) && (
                      <Field label="Database">
                        <Input value={formDatabase} onChange={(_, d) => setFormDatabase(d.value)}
                          placeholder="my-database" />
                      </Field>
                    )}

                    <Field label="Table or Query" required>
                      <Input value={formTableOrQuery} onChange={(_, d) => setFormTableOrQuery(d.value)}
                        placeholder="my_table  or  SELECT * FROM conversations" />
                    </Field>

                    <Field label="Display Name">
                      <Input value={formName} onChange={(_, d) => setFormName(d.value)}
                        placeholder={formTableOrQuery.split(/\s/)[0] || "My Data Source"} />
                    </Field>
                  </div>

                  {connectError && (
                    <div className="testResult testError">
                      <Dismiss24Regular /> {connectError}
                    </div>
                  )}
                </div>
              )}

              {/* ── Step 1: Preview & Confirm ── */}
              {wizardStep === 1 && createdSource && (
                <div className="wizardStep">
                  <div className="testResult testSuccess">
                    <Checkmark24Regular />{" "}
                    Connected to <strong>{createdSource.name}</strong> —{" "}
                    {createdSource.doc_count.toLocaleString()} rows found
                  </div>

                  {/* Sample data preview table */}
                  {sampleData.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <Text weight="semibold" size={300} style={{ color: "#334155" }}>
                        Sample data (auto-mapped)
                      </Text>
                      <div style={{ maxHeight: 220, overflow: "auto", marginTop: 8 }}>
                        <table className="sampleTable">
                          <thead>
                            <tr>
                              <th>ID</th>
                              <th>Text</th>
                              {fieldMapping.title_field && <th>Title</th>}
                              {fieldMapping.type_field && <th>Type</th>}
                            </tr>
                          </thead>
                          <tbody>
                            {sampleData.map((row, i) => (
                              <tr key={i}>
                                <td>{row.id}</td>
                                <td>{typeof row.text === "string"
                                  ? row.text.slice(0, 120)
                                  : JSON.stringify(row.text).slice(0, 120)}</td>
                                {fieldMapping.title_field && <td>{row.title || "—"}</td>}
                                {fieldMapping.type_field && <td>{row.type || "—"}</td>}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Auto-mapped fields summary */}
                  {suggestedMapping && (
                    <div className="autoMappedInfo">
                      <Text size={200} style={{ color: "#64748b" }}>
                        Auto-detected: <strong>{suggestedMapping.text_field}</strong> as content
                        {suggestedMapping.id_field !== "id" && (
                          <>, <strong>{suggestedMapping.id_field}</strong> as ID</>
                        )}
                        {suggestedMapping.title_field && (
                          <>, <strong>{suggestedMapping.title_field}</strong> as title</>
                        )}
                      </Text>
                    </div>
                  )}

                  {/* Advanced: override field mapping */}
                  <button className="advancedToggle" onClick={() => setShowAdvanced(!showAdvanced)}>
                    {showAdvanced ? <ChevronUp20Regular /> : <ChevronDown20Regular />}
                    <Settings20Regular /> Advanced options
                  </button>

                  {showAdvanced && columns.length > 0 && (
                    <div className="advancedPanel">
                      <div className="fieldRow">
                        <Field label="ID Column" size="small">
                          <Dropdown value={fieldMapping.id_field} size="small"
                            onOptionSelect={(_, d) => setFieldMapping((m) => ({
                              ...m, id_field: d.optionValue || "id",
                            }))}>
                            {columns.map((c) => (
                              <Option key={c.name} value={c.name} text={c.name}>{c.name}</Option>
                            ))}
                          </Dropdown>
                        </Field>
                        <Field label="Content Column" size="small">
                          <Dropdown value={fieldMapping.text_field} size="small"
                            onOptionSelect={(_, d) => setFieldMapping((m) => ({
                              ...m, text_field: d.optionValue || "text",
                            }))}>
                            {columns.map((c) => (
                              <Option key={c.name} value={c.name} text={c.name}>{c.name}</Option>
                            ))}
                          </Dropdown>
                        </Field>
                      </div>
                      <div className="fieldRow">
                        <Field label="Title Column" size="small">
                          <Dropdown value={fieldMapping.title_field || "(none)"} size="small"
                            onOptionSelect={(_, d) => setFieldMapping((m) => ({
                              ...m, title_field: d.optionValue === "(none)" ? "" : d.optionValue || "",
                            }))}>
                            <Option value="(none)" text="(none)">(none)</Option>
                            {columns.map((c) => (
                              <Option key={c.name} value={c.name} text={c.name}>{c.name}</Option>
                            ))}
                          </Dropdown>
                        </Field>
                        <Field label="Type Column" size="small">
                          <Dropdown value={fieldMapping.type_field || "(none)"} size="small"
                            onOptionSelect={(_, d) => setFieldMapping((m) => ({
                              ...m, type_field: d.optionValue === "(none)" ? "" : d.optionValue || "",
                            }))}>
                            <Option value="(none)" text="(none)">(none)</Option>
                            {columns.map((c) => (
                              <Option key={c.name} value={c.name} text={c.name}>{c.name}</Option>
                            ))}
                          </Dropdown>
                        </Field>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* ── Step 2: Success ── */}
              {wizardStep === 2 && createdSource && (
                <div className="wizardStep successStep">
                  <Checkmark24Regular style={{ fontSize: 48, color: "#059669" }} />
                  <h3 style={{ color: "#059669", margin: "12px 0 4px" }}>Data Source Connected!</h3>
                  <p style={{ color: "#64748b", fontSize: 14, marginBottom: 24 }}>
                    <strong>{createdSource.name}</strong> is ready with{" "}
                    {createdSource.doc_count.toLocaleString()} rows.
                    Your data is now searchable — ask questions or explore insights.
                  </p>
                  <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                    <Button appearance="primary" onClick={() => navigate("/explore")}>
                      Explore Your Data
                    </Button>
                    <Button appearance="outline" onClick={() => navigate("/insights")}>
                      View Insights
                    </Button>
                  </div>
                </div>
              )}
            </DialogContent>

            <DialogActions>
              {wizardStep === 0 && (
                <div className="wizardFooter" style={{ width: "100%" }}>
                  <div />
                  <div style={{ display: "flex", gap: 8 }}>
                    <Button appearance="subtle" onClick={() => setShowWizard(false)}>Cancel</Button>
                    <Button appearance="primary" onClick={handleConnect}
                      disabled={!canConnect || connecting}
                      icon={connecting ? <Spinner size="tiny" /> : <PlugConnected24Regular />}>
                      {connecting ? "Connecting..." : "Connect"}
                    </Button>
                  </div>
                </div>
              )}
              {wizardStep === 1 && (
                <div className="wizardFooter" style={{ width: "100%" }}>
                  <div />
                  <div style={{ display: "flex", gap: 8 }}>
                    <Button appearance="subtle"
                      onClick={() => { setShowWizard(false); resetWizard(); }}>
                      Done
                    </Button>
                    <Button appearance="primary" onClick={() => setWizardStep(2)}
                      icon={<Checkmark24Regular />}>
                      Looks Good
                    </Button>
                  </div>
                </div>
              )}
              {wizardStep === 2 && (
                <Button appearance="subtle"
                  onClick={() => { setShowWizard(false); resetWizard(); }}>
                  Close
                </Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
};

export default DataSources;
