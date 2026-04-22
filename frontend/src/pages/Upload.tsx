import React, { useState } from "react";
import {
  makeStyles,
  tokens,
  Text,
  Card,
  Button,
  Spinner,
  TabList,
  Tab,
  Badge,
} from "@fluentui/react-components";
import {
  ArrowUpload24Regular,
  DocumentSearch24Regular,
  Database24Regular,
} from "@fluentui/react-icons";
import DocumentUpload from "../components/DocumentUpload";
import FAQSearch from "../components/FAQSearch";
import { loadDefaultDataset, indexDocuments } from "../api/client";

const useStyles = makeStyles({
  container: {
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    maxWidth: "900px",
    margin: "0 auto",
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
  },
  quickActions: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "12px",
  },
  actionCard: {
    padding: "20px",
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusMedium,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    cursor: "pointer",
  },
  message: {
    padding: "12px 16px",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground1,
    border: `1px solid ${tokens.colorNeutralStroke1}`,
  },
});

const Upload: React.FC = () => {
  const styles = useStyles();
  const [activeTab, setActiveTab] = useState("upload");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleLoadAndIndex = async () => {
    setLoading(true);
    setMessage("");
    try {
      const ingestRes = await loadDefaultDataset();
      setMessage(`Loaded ${ingestRes.data.total_loaded} documents. Indexing...`);
      const indexRes = await indexDocuments();
      setMessage(
        `Done! Loaded ${ingestRes.data.total_loaded} docs, indexed ${indexRes.data.indexed_count} vectors.`
      );
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      setMessage(`Error: ${msg}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div>
          <Text size={500} weight="semibold">Upload Documents</Text>
          <Text block size={200} style={{ color: "#666", marginTop: 4 }}>
            Bring your own data — upload files or load the sample dataset
          </Text>
        </div>
      </div>

      {/* Quick actions */}
      <div className={styles.quickActions}>
        <div className={styles.actionCard} onClick={handleLoadAndIndex}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Database24Regular style={{ color: tokens.colorBrandForeground1 }} />
            <Text weight="semibold">Load & Index Sample Data</Text>
          </div>
          <Text size={200} style={{ color: "#666" }}>
            Load the built-in customer support dataset and index it for Q&A
          </Text>
          {loading && <Spinner size="tiny" />}
        </div>
        <div className={styles.actionCard} onClick={() => setActiveTab("extract")}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <DocumentSearch24Regular style={{ color: tokens.colorBrandForeground1 }} />
            <Text weight="semibold">Extract with Content Understanding</Text>
          </div>
          <Text size={200} style={{ color: "#666" }}>
            Upload PDF, DOCX, images, or audio for AI-powered extraction
          </Text>
        </div>
      </div>

      {message && (
        <div className={styles.message}>
          <Text size={200}>{message}</Text>
        </div>
      )}

      <TabList
        selectedValue={activeTab}
        onTabSelect={(_, data) => setActiveTab(data.value as string)}
      >
        <Tab value="upload" icon={<ArrowUpload24Regular />}>Upload JSON/CSV</Tab>
        <Tab value="extract" icon={<DocumentSearch24Regular />}>Extract Content</Tab>
        <Tab value="browse">Browse FAQs</Tab>
      </TabList>

      <div>
        {activeTab === "upload" && <DocumentUpload mode="ingest" />}
        {activeTab === "extract" && <DocumentUpload mode="extract" />}
        {activeTab === "browse" && <FAQSearch />}
      </div>
    </div>
  );
};

export default Upload;
