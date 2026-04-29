import React, { useState, useEffect } from "react";
import {
  Text,
  Button,
  makeStyles,
  tokens,
  Input,
  Dropdown,
  Option,
  Badge,
  Spinner,
  TabList,
  Tab,
} from "@fluentui/react-components";
import {
  Search24Regular,
  Dismiss24Regular,
  DocumentBulletList24Regular,
  TextDescription24Regular,
  TagMultiple24Regular,
  Info24Regular,
  Organization24Regular,
} from "@fluentui/react-icons";
import { getDocuments, getAvailableFilters, summarizeText, extractEntities } from "../api/client";

const useStyles = makeStyles({
  container: {
    display: "flex",
    flexDirection: "column",
    height: "100%",
    boxSizing: "border-box",
  },
  toolbar: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    flexWrap: "wrap",
    padding: "16px 24px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  listPanel: {
    width: "400px",
    flexShrink: 0,
    borderRight: `1px solid ${tokens.colorNeutralStroke2}`,
    overflowY: "auto",
    backgroundColor: tokens.colorNeutralBackground1,
  },
  docItem: {
    padding: "12px 20px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    cursor: "pointer",
    transition: "background-color 0.1s",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  docItemActive: {
    padding: "12px 20px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    cursor: "pointer",
    backgroundColor: "#eff6ff",
    borderLeft: "3px solid #2563eb",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
  },
  detailPanel: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    backgroundColor: "#f8fafc",
  },
  detailHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 24px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    flexShrink: 0,
  },
  detailTabs: {
    padding: "0 24px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    flexShrink: 0,
  },
  detailContent: {
    flex: 1,
    overflowY: "auto",
    padding: "20px 24px",
  },
  section: {
    marginBottom: "20px",
  },
  sectionTitle: {
    fontSize: "13px",
    fontWeight: "600",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
    color: "#64748b",
    marginBottom: "8px",
  },
  contentBlock: {
    padding: "18px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "8px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
    fontSize: "14px",
    lineHeight: "1.8",
    whiteSpace: "pre-wrap" as const,
    color: "#334155",
  },
  metaGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "12px",
  },
  metaCard: {
    padding: "12px 16px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "8px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
  },
  metaLabel: {
    fontSize: "12px",
    color: "#94a3b8",
    textTransform: "uppercase" as const,
    letterSpacing: "0.5px",
  },
  metaValue: {
    fontSize: "15px",
    fontWeight: "500",
    color: "#1e293b",
    marginTop: "2px",
  },
  entityList: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  entityRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    padding: "10px 14px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "8px",
    boxShadow: "0 1px 2px rgba(0,0,0,0.04)",
  },
  emptyDetail: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: "12px",
    color: "#94a3b8",
    padding: "48px",
    textAlign: "center" as const,
  },
  emptyList: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "48px 24px",
    gap: "12px",
    color: "#94a3b8",
    textAlign: "center" as const,
  },
  count: {
    fontSize: "13px",
    color: "#94a3b8",
    marginLeft: "auto",
  },
  badge: { textTransform: "capitalize" as const },
});

interface Doc {
  id: string;
  type: string;
  text: string | Array<{ speaker: string; text: string }>;
  metadata: {
    product?: string;
    category?: string;
    timestamp?: string;
    source_type?: string;
    source_file?: string;
    language?: string;
  };
}

interface Entity {
  text: string;
  type: string;
  confidence?: number;
}

const ENTITY_COLORS: Record<string, string> = {
  Person: "#2563eb",
  Organization: "#7c3aed",
  Product: "#059669",
  Location: "#d97706",
  Date: "#94a3b8",
  Issue: "#dc2626",
  Resolution: "#16a34a",
  Policy: "#6366f1",
  Amount: "#0891b2",
  "Reference Number": "#64748b",
};

const DataExplorer: React.FC = () => {
  const styles = useStyles();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Doc | null>(null);
  const [search, setSearch] = useState("");
  const [filters, setFilters] = useState<Record<string, string[]>>({});
  const [activeFilters, setActiveFilters] = useState<Record<string, string>>({});
  const [activeTab, setActiveTab] = useState("content");

  // Extraction results for selected doc
  const [summary, setSummary] = useState<string | null>(null);
  const [entities, setEntities] = useState<Entity[]>([]);
  const [extracting, setExtracting] = useState(false);

  const fetchFilters = async () => {
    try {
      const res = await getAvailableFilters();
      setFilters(res.data);
    } catch {
      // no filters
    }
  };

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (activeFilters.type) params.type = activeFilters.type;
      if (activeFilters.product) params.product = activeFilters.product;
      if (activeFilters.category) params.category = activeFilters.category;
      if (search) params.query = search;
      const res = await getDocuments(params);
      setDocs(res.data);
    } catch {
      setDocs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchFilters(); }, []);
  useEffect(() => { fetchDocs(); }, [activeFilters]);

  const handleSearch = () => fetchDocs();

  const normalizeText = (text: Doc["text"]): string => {
    if (typeof text === "string") return text;
    if (Array.isArray(text)) return text.map((s) => `${s.speaker}: ${s.text}`).join("\n");
    return String(text);
  };

  const handleSelect = async (doc: Doc) => {
    setSelected(doc);
    setSummary(null);
    setEntities([]);
    setActiveTab("content");
  };

  const handleExtract = async () => {
    if (!selected) return;
    setExtracting(true);
    const text = normalizeText(selected.text);
    try {
      const [sumRes, entRes] = await Promise.all([
        summarizeText(text, 150, "concise"),
        extractEntities(text),
      ]);
      setSummary(sumRes.data.summary);
      setEntities(entRes.data.entities);
    } catch {
      // extraction failed
    } finally {
      setExtracting(false);
    }
  };

  // Detect structure from text
  const getStructure = (doc: Doc) => {
    const text = normalizeText(doc.text);
    const lines = text.split("\n").filter((l) => l.trim());
    const sections: string[] = [];
    const headings: string[] = [];

    for (const line of lines) {
      if (line.startsWith("Q:") || line.startsWith("User:") || line.startsWith("Agent:")) {
        if (!sections.includes(line.split(":")[0] + " section")) {
          sections.push(line.split(":")[0] + " section");
        }
      }
      if (line.startsWith("#") || line === line.toUpperCase() && line.length > 3 && line.length < 60) {
        headings.push(line.replace(/^#+\s*/, ""));
      }
    }

    return {
      sections: sections.length > 0 ? sections : ["Main content"],
      headings: headings.length > 0 ? headings : ["(No headings detected)"],
      lineCount: lines.length,
      wordCount: text.split(/\s+/).length,
      isAudio: Array.isArray(doc.text),
      speakerCount: Array.isArray(doc.text) ? new Set(doc.text.map((s) => s.speaker)).size : 0,
    };
  };

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <Input
          placeholder="Search documents..."
          size="small"
          style={{ minWidth: 240 }}
          contentBefore={<Search24Regular />}
          value={search}
          onChange={(_, d) => setSearch(d.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Dropdown placeholder="Type" size="small" style={{ minWidth: 140 }} onOptionSelect={(_, d) => setActiveFilters((f) => ({ ...f, type: d.optionValue || "" }))}>
          <Option value="">All Types</Option>
          {(filters.type || []).map((t) => <Option key={t} value={t}>{t.replace(/_/g, " ")}</Option>)}
        </Dropdown>
        <Dropdown placeholder="Product" size="small" style={{ minWidth: 120 }} onOptionSelect={(_, d) => setActiveFilters((f) => ({ ...f, product: d.optionValue || "" }))}>
          <Option value="">All Products</Option>
          {(filters.product || []).map((p) => <Option key={p} value={p}>{p}</Option>)}
        </Dropdown>
        <Button size="small" onClick={handleSearch}>Search</Button>
        <span className={styles.count}>{docs.length} documents</span>
      </div>

      {/* Body: list + detail */}
      <div className={styles.body}>
        {/* Document List */}
        <div className={styles.listPanel}>
          {loading ? (
            <div className={styles.emptyList}><Spinner size="small" /></div>
          ) : docs.length === 0 ? (
            <div className={styles.emptyList}>
              <DocumentBulletList24Regular style={{ fontSize: 28 }} />
              <Text weight="semibold" size={200}>No documents</Text>
              <Text size={200}>Load data from the Home page.</Text>
            </div>
          ) : (
            docs.map((doc) => (
              <div
                key={doc.id}
                className={selected?.id === doc.id ? styles.docItemActive : styles.docItem}
                onClick={() => handleSelect(doc)}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <Text weight="semibold" size={200}>{doc.id}</Text>
                  <Badge appearance="tint" color="brand" size="small" className={styles.badge}>
                    {doc.type.replace(/_/g, " ")}
                  </Badge>
                </div>
                <Text size={100} style={{ color: "#94a3b8" }}>
                  {doc.metadata.product || "No product"} · {doc.metadata.category || "No category"}
                </Text>
              </div>
            ))
          )}
        </div>

        {/* Detail / Extraction View */}
        <div className={styles.detailPanel}>
          {!selected ? (
            <div className={styles.emptyDetail}>
              <DocumentBulletList24Regular style={{ fontSize: 36 }} />
              <Text weight="semibold" size={300}>Select a document</Text>
              <Text size={200}>Click a document from the list to view extraction details.</Text>
            </div>
          ) : (
            <>
              {/* Header */}
              <div className={styles.detailHeader}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <Text weight="semibold" size={400}>{selected.id}</Text>
                  <Badge appearance="tint" color="brand" size="small" className={styles.badge}>
                    {selected.type.replace(/_/g, " ")}
                  </Badge>
                  {selected.metadata.product && (
                    <Badge appearance="outline" size="small">{selected.metadata.product}</Badge>
                  )}
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  <Button
                    appearance="primary"
                    size="small"
                    onClick={handleExtract}
                    disabled={extracting}
                  >
                    {extracting ? <Spinner size="tiny" /> : "Run Extraction"}
                  </Button>
                  <Button appearance="subtle" size="small" icon={<Dismiss24Regular />} onClick={() => setSelected(null)} />
                </div>
              </div>

              {/* Tabs */}
              <div className={styles.detailTabs}>
                <TabList
                  selectedValue={activeTab}
                  onTabSelect={(_, d) => setActiveTab(d.value as string)}
                  size="small"
                >
                  <Tab value="content" icon={<TextDescription24Regular />}>Content</Tab>
                  <Tab value="structure" icon={<Organization24Regular />}>Structure</Tab>
                  <Tab value="entities" icon={<TagMultiple24Regular />}>Entities</Tab>
                  <Tab value="metadata" icon={<Info24Regular />}>Metadata</Tab>
                </TabList>
              </div>

              {/* Tab Content */}
              <div className={styles.detailContent}>
                {activeTab === "content" && (
                  <>
                    {summary && (
                      <div className={styles.section}>
                        <div className={styles.sectionTitle}>Summary</div>
                        <div className={styles.contentBlock} style={{ borderLeft: "3px solid #2563eb" }}>
                          {summary}
                        </div>
                      </div>
                    )}
                    <div className={styles.section}>
                      <div className={styles.sectionTitle}>Extracted Text</div>
                      <div className={styles.contentBlock}>
                        {normalizeText(selected.text)}
                      </div>
                    </div>
                  </>
                )}

                {activeTab === "structure" && (() => {
                  const struct = getStructure(selected);
                  return (
                    <>
                      <div className={styles.section}>
                        <div className={styles.sectionTitle}>Document Stats</div>
                        <div className={styles.metaGrid}>
                          <div className={styles.metaCard}>
                            <div className={styles.metaLabel}>Lines</div>
                            <div className={styles.metaValue}>{struct.lineCount}</div>
                          </div>
                          <div className={styles.metaCard}>
                            <div className={styles.metaLabel}>Words</div>
                            <div className={styles.metaValue}>{struct.wordCount}</div>
                          </div>
                          {struct.isAudio && (
                            <div className={styles.metaCard}>
                              <div className={styles.metaLabel}>Speakers</div>
                              <div className={styles.metaValue}>{struct.speakerCount}</div>
                            </div>
                          )}
                          <div className={styles.metaCard}>
                            <div className={styles.metaLabel}>Format</div>
                            <div className={styles.metaValue}>
                              {struct.isAudio ? "Audio Transcript" : "Text"}
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className={styles.section}>
                        <div className={styles.sectionTitle}>Detected Sections</div>
                        <div className={styles.entityList}>
                          {struct.sections.map((s, i) => (
                            <div key={i} className={styles.entityRow}>
                              <Badge appearance="tint" color="brand" size="small">{i + 1}</Badge>
                              <Text size={200}>{s}</Text>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className={styles.section}>
                        <div className={styles.sectionTitle}>Headings</div>
                        <div className={styles.entityList}>
                          {struct.headings.map((h, i) => (
                            <div key={i} className={styles.entityRow}>
                              <Text size={200} weight="semibold">{h}</Text>
                            </div>
                          ))}
                        </div>
                      </div>
                    </>
                  );
                })()}

                {activeTab === "entities" && (
                  <>
                    {entities.length === 0 && !extracting ? (
                      <div className={styles.emptyDetail}>
                        <TagMultiple24Regular style={{ fontSize: 32 }} />
                        <Text weight="semibold" size={200}>No entities extracted yet</Text>
                        <Text size={200}>Click "Run Extraction" to detect entities.</Text>
                      </div>
                    ) : extracting ? (
                      <div className={styles.emptyDetail}><Spinner size="small" label="Extracting..." /></div>
                    ) : (
                      <div className={styles.entityList}>
                        {entities.map((e, i) => (
                          <div key={i} className={styles.entityRow}>
                            <Badge
                              appearance="filled"
                              size="small"
                              style={{
                                backgroundColor: ENTITY_COLORS[e.type] || "#64748b",
                                color: "white",
                                minWidth: 90,
                                textAlign: "center",
                              }}
                            >
                              {e.type}
                            </Badge>
                            <Text size={200} weight="semibold" style={{ flex: 1 }}>{e.text}</Text>
                            {e.confidence != null && (
                              <Text size={100} style={{ color: "#94a3b8" }}>
                                {(e.confidence * 100).toFixed(0)}%
                              </Text>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}

                {activeTab === "metadata" && (
                  <div className={styles.metaGrid}>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Document ID</div>
                      <div className={styles.metaValue}>{selected.id}</div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Type</div>
                      <div className={styles.metaValue} style={{ textTransform: "capitalize" }}>
                        {selected.type.replace(/_/g, " ")}
                      </div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Product</div>
                      <div className={styles.metaValue}>{selected.metadata.product || "—"}</div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Category</div>
                      <div className={styles.metaValue} style={{ textTransform: "capitalize" }}>
                        {selected.metadata.category || "—"}
                      </div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Source Type</div>
                      <div className={styles.metaValue}>{selected.metadata.source_type || "—"}</div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Source File</div>
                      <div className={styles.metaValue}>{selected.metadata.source_file || "—"}</div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Language</div>
                      <div className={styles.metaValue}>{selected.metadata.language || "Auto-detected"}</div>
                    </div>
                    <div className={styles.metaCard}>
                      <div className={styles.metaLabel}>Timestamp</div>
                      <div className={styles.metaValue}>{selected.metadata.timestamp || "—"}</div>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default DataExplorer;
