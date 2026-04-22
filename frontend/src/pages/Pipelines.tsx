import React, { useState, useEffect } from "react";
import {
  Text,
  Button,
  makeStyles,
  tokens,
  Spinner,
  Badge,
} from "@fluentui/react-components";
import {
  Play24Regular,
  Checkmark24Regular,
  Dismiss24Regular,
  ArrowRight16Regular,
  Clock24Regular,
} from "@fluentui/react-icons";
import { listPipelines, runPipeline } from "../api/client";

const useStyles = makeStyles({
  container: {
    padding: "24px 32px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
    maxWidth: "1000px",
  },
  pipelineCard: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: "12px",
    boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
    overflow: "hidden",
  },
  cardHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "20px 24px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
  },
  stepsRow: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "20px 24px",
    overflowX: "auto",
  },
  stepBox: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#f8fafc",
    border: "1px solid #e2e8f0",
    minWidth: "110px",
    textAlign: "center" as const,
    flexShrink: 0,
    transition: "all 0.2s",
  },
  stepSuccess: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#f0fdf4",
    border: "1px solid #bbf7d0",
    minWidth: "110px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  stepError: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#fef2f2",
    border: "1px solid #fecaca",
    minWidth: "110px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  stepRunning: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "6px",
    padding: "12px 16px",
    borderRadius: "10px",
    backgroundColor: "#eff6ff",
    border: "1px solid #bfdbfe",
    minWidth: "110px",
    textAlign: "center" as const,
    flexShrink: 0,
  },
  arrow: {
    color: "#cbd5e1",
    flexShrink: 0,
  },
  resultBar: {
    padding: "12px 24px",
    borderTop: `1px solid ${tokens.colorNeutralStroke2}`,
    fontSize: "12px",
    color: "#64748b",
    display: "flex",
    alignItems: "center",
    gap: "8px",
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
}

const Pipelines: React.FC = () => {
  const styles = useStyles();
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [results, setResults] = useState<Record<string, RunResult>>({});
  const [running, setRunning] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await listPipelines();
        setPipelines(res.data);
      } catch {
        // ignore
      }
    };
    load();
  }, []);

  const handleRun = async (name: string) => {
    setRunning(name);
    setResults((prev) => ({ ...prev, [name]: undefined as unknown as RunResult }));
    try {
      const res = await runPipeline(name);
      setResults((prev) => ({ ...prev, [name]: res.data }));
    } catch (error: unknown) {
      const msg = error instanceof Error ? error.message : "Failed";
      setResults((prev) => ({
        ...prev,
        [name]: { pipeline_name: name, status: "error", steps: [{ step_name: "run", status: "error", message: msg }] },
      }));
    } finally {
      setRunning(null);
    }
  };

  const getStepStyle = (pipelineName: string, stepName: string) => {
    const result = results[pipelineName];
    if (!result) return styles.stepBox;
    if (running === pipelineName) return styles.stepRunning;
    const stepResult = result.steps.find((s) => s.step_name === stepName);
    if (!stepResult) return styles.stepBox;
    if (stepResult.status === "success") return styles.stepSuccess;
    if (stepResult.status === "error") return styles.stepError;
    return styles.stepBox;
  };

  const getStepIcon = (pipelineName: string, stepName: string) => {
    const result = results[pipelineName];
    if (!result) return null;
    const stepResult = result.steps.find((s) => s.step_name === stepName);
    if (!stepResult) return null;
    if (stepResult.status === "success") return <Checkmark24Regular style={{ color: "#16a34a", fontSize: 14 }} />;
    if (stepResult.status === "error") return <Dismiss24Regular style={{ color: "#dc2626", fontSize: 14 }} />;
    return null;
  };

  return (
    <div className={styles.container}>
      <div>
        <Text size={200} style={{ color: "#64748b" }}>
          Select a pipeline and run it. Each pipeline defines a reusable sequence of AI operations.
        </Text>
      </div>

      {pipelines.map((p) => (
        <div key={p.name} className={styles.pipelineCard}>
          <div className={styles.cardHeader}>
            <div>
              <Text weight="semibold" size={400}>{p.name.replace(/_/g, " ")}</Text>
              <Text block size={200} style={{ color: "#64748b", marginTop: 2 }}>{p.description}</Text>
            </div>
            <Button
              appearance="primary"
              size="small"
              icon={running === p.name ? undefined : <Play24Regular />}
              onClick={() => handleRun(p.name)}
              disabled={running !== null}
            >
              {running === p.name ? <Spinner size="tiny" /> : "Run"}
            </Button>
          </div>

          {/* Visual step flow */}
          <div className={styles.stepsRow}>
            {p.steps.map((step, i) => (
              <React.Fragment key={step.name}>
                <div className={getStepStyle(p.name, step.name)}>
                  {getStepIcon(p.name, step.name)}
                  <Text size={200} weight="semibold" style={{ textTransform: "capitalize" }}>
                    {step.name.replace(/_/g, " ")}
                  </Text>
                  <Text size={100} style={{ color: "#94a3b8" }}>
                    {step.action.replace(/_/g, " ")}
                  </Text>
                </div>
                {i < p.steps.length - 1 && (
                  <ArrowRight16Regular className={styles.arrow} />
                )}
              </React.Fragment>
            ))}
          </div>

          {/* Result bar */}
          {results[p.name] && (
            <div className={styles.resultBar}>
              <Badge
                appearance="tint"
                color={results[p.name].status === "success" ? "success" : "danger"}
                size="small"
              >
                {results[p.name].status}
              </Badge>
              {results[p.name].steps.map((s, i) => (
                <span key={i}>
                  {s.step_name}: {s.status === "success" ? "✓" : "✗"}{" "}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}

      {pipelines.length === 0 && (
        <div style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
          <Clock24Regular style={{ fontSize: 32, marginBottom: 8 }} />
          <Text block weight="semibold">No pipelines configured</Text>
          <Text block size={200}>Add YAML pipeline configs to backend/app/config/use_cases/</Text>
        </div>
      )}
    </div>
  );
};

export default Pipelines;
