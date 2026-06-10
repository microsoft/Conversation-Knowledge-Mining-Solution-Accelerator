import React, { Component, ErrorInfo, ReactNode } from "react";
import { Button } from "@fluentui/react-components";
import { ErrorCircle24Regular } from "@fluentui/react-icons";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div style={{
          display: "flex", flexDirection: "column", alignItems: "center",
          justifyContent: "center", gap: 16, padding: 48, textAlign: "center",
        }}>
          <ErrorCircle24Regular style={{ fontSize: 48, color: "#dc2626" }} />
          <h2 style={{ margin: 0, fontWeight: 600 }}>Something went wrong</h2>
          <p style={{ color: "#64748b", margin: 0 }}>
            An unexpected error occurred. Please try refreshing the page.
          </p>
          <Button appearance="primary" onClick={this.handleReset}>
            Try again
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
