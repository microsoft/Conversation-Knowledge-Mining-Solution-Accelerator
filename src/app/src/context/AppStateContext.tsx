import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from "react";
import { loadFromSession } from "../utils/storage";
import type { DashboardResponse, ChatMessage } from "../types/api";
import { getUploadedFiles, listDataSources, getExtractionInfo } from "../api/client";

interface AppState {
  // Insights cache
  insights: DashboardResponse | null;
  setInsights: (data: DashboardResponse | null) => void;

  // Dashboard headline (LLM-generated, shown in app header)
  dashboardHeadline: string;
  setDashboardHeadline: (h: string) => void;

  // Chat cache (global chat on Insights page)
  chatMessages: ChatMessage[];
  setChatMessages: (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;

  // Explore chat cache
  exploreChatMessages: ChatMessage[];
  setExploreChatMessages: (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;

  // Explore data cache (files, data sources, schema)
  exploreData: { files: any[]; dataSources: any[]; schema: any } | null;
  setExploreData: (d: { files: any[]; dataSources: any[]; schema: any } | null) => void;

  // Home data cache (data sources, uploaded files)
  homeData: { dataSources: any[]; uploadedFiles: any[] } | null;
  setHomeData: (d: { dataSources: any[]; uploadedFiles: any[] } | null) => void;

  // Shared ingestion snapshot (single global polling source)
  ingestionSnapshot: { uploadedFiles: any[]; dataSources: any[]; schema: any; updatedAt: number } | null;
}

const AppContext = createContext<AppState>({
  insights: null,
  setInsights: () => {},
  dashboardHeadline: "",
  setDashboardHeadline: () => {},
  chatMessages: [],
  setChatMessages: () => {},
  exploreChatMessages: [],
  setExploreChatMessages: () => {},
  exploreData: null,
  setExploreData: () => {},
  homeData: null,
  setHomeData: () => {},
  ingestionSnapshot: null,
});

export const useAppState = () => useContext(AppContext);

export const AppStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [insights, setInsightsRaw] = useState<DashboardResponse | null>(() => loadFromSession("km_insights", null));
  const [dashboardHeadline, setDashboardHeadline] = useState<string>(() => loadFromSession("km_headline", ""));
  const [chatMessages, setChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_chat", []));
  const [exploreChatMessages, setExploreChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_explore_chat", []));
  const [exploreData, setExploreDataRaw] = useState<{ files: any[]; dataSources: any[]; schema: any } | null>(() => loadFromSession("km_explore_data", null));
  const [homeData, setHomeDataRaw] = useState<{ dataSources: any[]; uploadedFiles: any[] } | null>(() => loadFromSession("km_home_data", null));
  const [ingestionSnapshot, setIngestionSnapshot] = useState<{ uploadedFiles: any[]; dataSources: any[]; schema: any; updatedAt: number } | null>(null);
  const snapshotRef = useRef<typeof ingestionSnapshot>(null);
  const homeDataRef = useRef<typeof homeData>(homeData);
  const exploreDataRef = useRef<typeof exploreData>(exploreData);

  useEffect(() => {
    snapshotRef.current = ingestionSnapshot;
  }, [ingestionSnapshot]);

  useEffect(() => {
    homeDataRef.current = homeData;
  }, [homeData]);

  useEffect(() => {
    exploreDataRef.current = exploreData;
  }, [exploreData]);

  const setInsights = (data: DashboardResponse | null) => {
    setInsightsRaw(data);
    try { sessionStorage.setItem("km_insights", JSON.stringify(data)); } catch {}
  };

  const setChatMessages = (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    setChatMessagesRaw((prev) => {
      const next = typeof msgs === "function" ? msgs(prev) : msgs;
      try { sessionStorage.setItem("km_chat", JSON.stringify(next)); } catch {}
      return next;
    });
  };

  const setExploreChatMessages = (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
    setExploreChatMessagesRaw((prev) => {
      const next = typeof msgs === "function" ? msgs(prev) : msgs;
      try { sessionStorage.setItem("km_explore_chat", JSON.stringify(next)); } catch {}
      return next;
    });
  };

  const setExploreData = useCallback((d: { files: any[]; dataSources: any[]; schema: any } | null) => {
    setExploreDataRaw(d);
    try { sessionStorage.setItem("km_explore_data", JSON.stringify(d)); } catch {}
  }, []);

  const setHomeData = useCallback((d: { dataSources: any[]; uploadedFiles: any[] } | null) => {
    setHomeDataRaw(d);
    try { sessionStorage.setItem("km_home_data", JSON.stringify(d)); } catch {}
  }, []);

  useEffect(() => {
    let timer: number | null = null;

    const tick = async () => {
      // Poll while processing is active OR while app has no known data yet,
      // so externally triggered scenario loads become visible without reload.
      const cachedFiles = snapshotRef.current?.uploadedFiles
        ?? homeDataRef.current?.uploadedFiles
        ?? exploreDataRef.current?.files
        ?? [];
      const cachedSources = snapshotRef.current?.dataSources
        ?? homeDataRef.current?.dataSources
        ?? exploreDataRef.current?.dataSources
        ?? [];

      const hasProcessing = cachedFiles.some((f: any) => f.status === "processing");
      const hasAnyData = cachedFiles.length > 0 || cachedSources.length > 0;
      if (!hasProcessing && hasAnyData) return;

      try {
        const filesRes = await getUploadedFiles();
        const files = Array.isArray(filesRes.data) ? filesRes.data : [];

        const stillProcessing = files.some((f: any) => f.status === "processing");

        // Still empty and no active processing: keep waiting without extra calls.
        if (!stillProcessing && files.length === 0 && !hasAnyData) return;

        let dataSources = snapshotRef.current?.dataSources ?? homeDataRef.current?.dataSources ?? exploreDataRef.current?.dataSources ?? [];
        let schema = snapshotRef.current?.schema ?? exploreDataRef.current?.schema ?? null;

        // Refresh heavier endpoints only when processing completes.
        if (!stillProcessing) {
          try {
            const [srcRes, schemaRes] = await Promise.all([listDataSources(), getExtractionInfo()]);
            dataSources = Array.isArray(srcRes.data) ? srcRes.data : dataSources;
            schema = schemaRes.data ?? schema;
          } catch {
            // Keep cached values if refresh fails.
          }
        }

        const snapshot = { uploadedFiles: files, dataSources, schema, updatedAt: Date.now() };
        setIngestionSnapshot(snapshot);
      } catch {
        // Ignore transient polling errors.
      }
    };

    // Fast no-op interval when nothing is processing; active updates when processing exists.
    timer = window.setInterval(tick, 10000);
    tick();

    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, []);

  return (
    <AppContext.Provider value={{
      insights, setInsights,
      dashboardHeadline, setDashboardHeadline,
      chatMessages, setChatMessages,
      exploreChatMessages, setExploreChatMessages,
      exploreData, setExploreData,
      homeData, setHomeData,
      ingestionSnapshot,
    }}>
      {children}
    </AppContext.Provider>
  );
};
