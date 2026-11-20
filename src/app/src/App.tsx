import React, { Suspense, lazy } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import ErrorBoundary from "./components/ErrorBoundary";
import { AppStateProvider } from "./context/AppStateContext";
import { Spinner } from "@fluentui/react-components";
import SessionBoundary from "./auth/SessionBoundary";

const Home = lazy(() => import("./pages/Home"));
const Explore = lazy(() => import("./pages/Explore"));
const Insights = lazy(() => import("./pages/Insights"));

const PageFallback = () => (
  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh" }}>
    <Spinner size="large" label="Loading..." />
  </div>
);

const App: React.FC = () => {
  return (
    <SessionBoundary>
    <AppStateProvider>
    <BrowserRouter>
      <Layout>
        <ErrorBoundary>
        <Suspense fallback={<PageFallback />}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/explore" element={<Explore />} />
        </Routes>
        </Suspense>
        </ErrorBoundary>
      </Layout>
    </BrowserRouter>
    </AppStateProvider>
    </SessionBoundary>
  );
};

export default App;