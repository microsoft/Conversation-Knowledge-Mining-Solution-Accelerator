import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Explore from "./pages/Explore";
import Insights from "./pages/Insights";
import { AppStateProvider } from "./context/AppStateContext";

const App: React.FC = () => {
  return (
    <AppStateProvider>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/explore" element={<Explore />} />
        </Routes>
      </Layout>
    </BrowserRouter>
    </AppStateProvider>
  );
};

export default App;
