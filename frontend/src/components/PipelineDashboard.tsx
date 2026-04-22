import React, { useState, useEffect } from "react";
import {
  Button,
  Card,
  CardHeader,
  Text,
  Spinner,
  Badge,
  makeStyles,
  tokens,
} from "@fluentui/react-components";
import { Play24Regular } from "@fluentui/react-icons";
import { listPipelines, runPipeline } from "../api/client";

const useStyles = makeStyles({
  container: { display: "flex", flexDirection: "column", gap: "16px" },
  stepResult: {
    padding: "8px 12px",
    borderRadius: tokens.borderRadiusMedium,
    backgroundColor: tokens.colorNeutralBackground3,
    marginTop: "4px",
  },
});

interface PipelineStep {
  name: string;
  action: string;
  description?: string;
}

interface Pipeline {
  name: string;
  description: string;
  steps: PipelineStep[];
}

interface StepResult {
  step_name: string;
  status: string;
  message: string;
}

interface RunResult {
  pipeline_name: string;
  status: string;
  steps: StepResult[];
  error?: string;
}

const PipelineDashboard: React.FC = () => {
  const styles = useStyles();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [runResults, setRunResults] = useState<Record<string, RunResult>>({});
  const [running, setRunning] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const response = await listPipelines();
        setPipelines(response.data);
      } catch {
        // ignore
      }
    };
    load();
  }, []);

  const handleRun = async (name: string) => {
    setRunning(name);
    try {
      const response = await runPipeline(name);
      setRunResults((prev) => ({ ...prev, [name]: response.data }));
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Unknown error";
      setRunResults((prev) => ({
        ...prev,
        [name]: { pipeline_name: name, status: "error", steps: [], error: msg },
      }));
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className={styles.container}>
      {pipelines.map((p) => (
        <Card key={p.name}>
          <CardHeader
            header={<Text weight="semibold">{p.name}</Text>}
            description={<Text size={200}>{p.description}</Text>}
            action={
              <Button
                appearance="primary"
                icon={<Play24Regular />}
                onClick={() => handleRun(p.name)}
                disabled={running === p.name}
              >
                {running === p.name ? "Running..." : "Run"}
              </Button>
            }
          />
          <div style={{ padding: "0 16px 16px" }}>
            <Text size={200} weight="semibold">Steps:</Text>
            {p.steps?.map((step, i) => (
              <Text key={i} size={200} block>
                {i + 1}. {step.name} → {step.action}
              </Text>
            ))}
          </div>
          {running === p.name && <Spinner size="small" />}
          {runResults[p.name] && (
            <div style={{ padding: "0 16px 16px" }}>
              <Text weight="semibold" size={200}>
                Result:{" "}
                <Badge
                  appearance={runResults[p.name].status === "success" ? "filled" : "tint"}
                  color={runResults[p.name].status === "success" ? "success" : "danger"}
                >
                  {runResults[p.name].status}
                </Badge>
              </Text>
              {runResults[p.name].steps?.map((step, i) => (
                <div key={i} className={styles.stepResult}>
                  <Text size={200}>{step.step_name}: {step.status} — {step.message}</Text>
                </div>
              ))}
            </div>
          )}
        </Card>
      ))}
      {pipelines.length === 0 && <Text italic>No pipelines configured.</Text>}
    </div>
  );
};

export default PipelineDashboard;
