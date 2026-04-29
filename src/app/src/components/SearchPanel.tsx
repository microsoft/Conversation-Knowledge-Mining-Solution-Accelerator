import React, { useState } from "react";
import {
  makeStyles,
  Input,
  Button,
  Card,
  CardHeader,
  Text,
  Spinner,
  Dropdown,
  Option,
} from "@fluentui/react-components";
import { Search24Regular } from "@fluentui/react-icons";
import { vectorSearch } from "../api/client";

const useStyles = makeStyles({
  container: { display: "flex", flexDirection: "column", gap: "16px" },
  searchRow: { display: "flex", gap: "8px", flexWrap: "wrap" },
  results: { display: "flex", flexDirection: "column", gap: "8px" },
});

interface Result {
  doc_id: string;
  score: number;
  text: string;
  metadata: { type?: string; product?: string; category?: string };
  error?: string;
}

const SearchPanel: React.FC = () => {
  const styles = useStyles();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [productFilter, setProductFilter] = useState<string>("");

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const filters = productFilter ? { product: productFilter } : undefined;
      const response = await vectorSearch(query, 5, filters);
      setResults(response.data);
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      setResults([{ doc_id: "", score: 0, text: "", metadata: {}, error: msg }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.searchRow}>
        <Input
          style={{ flex: 1 }}
          placeholder="Search knowledge base..."
          value={query}
          onChange={(_, data) => setQuery(data.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
        />
        <Dropdown
          placeholder="Filter by product"
          onOptionSelect={(_, data) => setProductFilter(data.optionValue || "")}
        >
          <Option value="">All Products</Option>
          <Option value="ZX-3000">ZX-3000</Option>
          <Option value="ZX-Fiber">ZX-Fiber</Option>
          <Option value="Printer-X">Printer-X</Option>
          <Option value="Router-Y">Router-Y</Option>
        </Dropdown>
        <Button appearance="primary" icon={<Search24Regular />} onClick={handleSearch} disabled={loading}>
          Search
        </Button>
      </div>
      {loading && <Spinner label="Searching..." />}
      <div className={styles.results}>
        {results.map((r, i) => (
          <Card key={i}>
            <CardHeader
              header={<Text weight="semibold">{r.doc_id} — Score: {r.score?.toFixed(4)}</Text>}
              description={
                <Text size={200}>
                  {r.metadata?.type} | {r.metadata?.product} | {r.metadata?.category}
                </Text>
              }
            />
            <Text style={{ padding: "0 16px 16px" }} size={200}>{r.text}</Text>
          </Card>
        ))}
      </div>
    </div>
  );
};

export default SearchPanel;
