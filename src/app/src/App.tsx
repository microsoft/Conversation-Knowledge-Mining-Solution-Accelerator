import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Explore from "./pages/Explore";
import Insights from "./pages/Insights";
import DataSources from "./pages/DataSources/DataSources";
import { AppStateProvider } from "./context/AppStateContext";

const App: React.FC = () => {
  return (
    <AppStateProvider>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/explore" element={<Explore />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/data-sources" element={<DataSources />} />
        </Routes>
      </Layout>
    </BrowserRouter>
    </AppStateProvider>
  );
};

export default App;
