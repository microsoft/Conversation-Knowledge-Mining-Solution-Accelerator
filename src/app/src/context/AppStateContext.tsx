import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { loadFromSession } from "../utils/storage";
import type { DashboardResponse, ChatMessage } from "../types/api";

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
});

export const useAppState = () => useContext(AppContext);

export const AppStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [insights, setInsightsRaw] = useState<DashboardResponse | null>(() => loadFromSession("km_insights", null));
  const [dashboardHeadline, setDashboardHeadline] = useState<string>(() => loadFromSession("km_headline", ""));
  const [chatMessages, setChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_chat", []));
  const [exploreChatMessages, setExploreChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_explore_chat", []));
  const [exploreData, setExploreDataRaw] = useState<{ files: any[]; dataSources: any[]; schema: any } | null>(() => loadFromSession("km_explore_data", null));
  const [homeData, setHomeDataRaw] = useState<{ dataSources: any[]; uploadedFiles: any[] } | null>(() => loadFromSession("km_home_data", null));

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

  const setExploreData = (d: { files: any[]; dataSources: any[]; schema: any } | null) => {
    setExploreDataRaw(d);
    try { sessionStorage.setItem("km_explore_data", JSON.stringify(d)); } catch {}
  };

  const setHomeData = (d: { dataSources: any[]; uploadedFiles: any[] } | null) => {
    setHomeDataRaw(d);
    try { sessionStorage.setItem("km_home_data", JSON.stringify(d)); } catch {}
  };

  return (
    <AppContext.Provider value={{
      insights, setInsights,
      dashboardHeadline, setDashboardHeadline,
      chatMessages, setChatMessages,
      exploreChatMessages, setExploreChatMessages,
      exploreData, setExploreData,
      homeData, setHomeData,
    }}>
      {children}
    </AppContext.Provider>
  );
};
