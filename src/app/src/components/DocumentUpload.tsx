import React, { useRef, useState } from "react";
import {
  Button,
  Text,
  makeStyles,
  tokens,
  Spinner,
} from "@fluentui/react-components";
import { ArrowUpload24Regular } from "@fluentui/react-icons";
import { uploadJsonFile, uploadCsvFile, extractDocument } from "../api/client";
import {
  SUPPORTED_INGEST_ACCEPT,
  SUPPORTED_EXTRACT_ACCEPT,
  SUPPORTED_EXTRACT_DESCRIPTION,
} from "../utils/constants";

const useStyles = makeStyles({
  dropZone: {
    border: `2px dashed ${tokens.colorNeutralStroke1}`,
    borderRadius: tokens.borderRadiusMedium,
    padding: "40px",
    textAlign: "center",
    cursor: "pointer",
  },
  result: {
    marginTop: "16px",
    padding: "12px",
    backgroundColor: tokens.colorNeutralBackground3,
    borderRadius: tokens.borderRadiusMedium,
  },
});

interface Props {
  mode: "ingest" | "extract";
  onComplete?: (data: unknown) => void;
}

const DocumentUpload: React.FC<Props> = ({ mode, onComplete }) => {
  const styles = useStyles();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const isCsv = file.name.toLowerCase().endsWith(".csv");
      const response = mode === "ingest"
        ? (isCsv ? await uploadCsvFile(file) : await uploadJsonFile(file))
        : await extractDocument(file);
      setResult(response.data);
      onComplete?.(response.data);
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      setResult({ error: msg });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className={styles.dropZone} onClick={() => fileInputRef.current?.click()}>
        <ArrowUpload24Regular />
        <br />
        <Text>
          {mode === "ingest"
            ? "Click to upload JSON/CSV for ingestion"
            : `Click to upload ${SUPPORTED_EXTRACT_DESCRIPTION} for extraction`}
        </Text>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: "none" }}
          accept={mode === "ingest" ? SUPPORTED_INGEST_ACCEPT : SUPPORTED_EXTRACT_ACCEPT}
          onChange={handleFileSelect}
        />
      </div>
      {loading && <Spinner style={{ marginTop: 16 }} label="Processing..." />}
      {result && (
        <div className={styles.result}>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default DocumentUpload;
