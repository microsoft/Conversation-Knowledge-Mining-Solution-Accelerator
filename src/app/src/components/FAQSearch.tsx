import React, { useState, useEffect } from "react";
import {
  Input,
  Card,
  CardHeader,
  Text,
  makeStyles,
} from "@fluentui/react-components";
import { getDocuments } from "../api/client";

const useStyles = makeStyles({
  container: { display: "flex", flexDirection: "column", gap: "12px" },
});

interface FAQ {
  id: string;
  text: string;
  metadata: { product?: string; category?: string };
}

const FAQSearch: React.FC = () => {
  const styles = useStyles();
  const [faqs, setFaqs] = useState<FAQ[]>([]);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    const loadFaqs = async () => {
      try {
        const response = await getDocuments({ type: "faq_document" });
        setFaqs(response.data);
      } catch {
        // ignore
      }
    };
    loadFaqs();
  }, []);

  const filtered = faqs.filter((faq) =>
    filter
      ? typeof faq.text === "string" && faq.text.toLowerCase().includes(filter.toLowerCase())
      : true
  );

  return (
    <div className={styles.container}>
      <Input
        placeholder="Search FAQs..."
        value={filter}
        onChange={(_, data) => setFilter(data.value)}
      />
      {filtered.map((faq) => (
        <Card key={faq.id}>
          <CardHeader
            header={<Text weight="semibold">{faq.id}</Text>}
            description={
              <Text size={200}>
                {faq.metadata?.product} | {faq.metadata?.category}
              </Text>
            }
          />
          <Text style={{ padding: "0 16px 16px", whiteSpace: "pre-wrap" }} size={200}>
            {faq.text}
          </Text>
        </Card>
      ))}
      {filtered.length === 0 && <Text italic>No FAQs found. Load data first.</Text>}
    </div>
  );
};

export default FAQSearch;
