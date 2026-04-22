import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sources?: Array<{ doc_id: string; score: number }>;
}

interface AppState {
  // Insights cache
  insights: any | null;
  setInsights: (data: any) => void;

  // Chat cache (global chat on Insights page)
  chatMessages: ChatMessage[];
  setChatMessages: (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;

  // Explore chat cache
  exploreChatMessages: ChatMessage[];
  setExploreChatMessages: (msgs: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => void;
}

const AppContext = createContext<AppState>({
  insights: null,
  setInsights: () => {},
  chatMessages: [],
  setChatMessages: () => {},
  exploreChatMessages: [],
  setExploreChatMessages: () => {},
});

export const useAppState = () => useContext(AppContext);

function loadFromSession<T>(key: string, fallback: T): T {
  try {
    const stored = sessionStorage.getItem(key);
    return stored ? JSON.parse(stored) : fallback;
  } catch {
    return fallback;
  }
}

export const AppStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [insights, setInsightsRaw] = useState<any | null>(() => loadFromSession("km_insights", null));
  const [chatMessages, setChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_chat", []));
  const [exploreChatMessages, setExploreChatMessagesRaw] = useState<ChatMessage[]>(() => loadFromSession("km_explore_chat", []));

  const setInsights = (data: any) => {
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

  return (
    <AppContext.Provider value={{
      insights, setInsights,
      chatMessages, setChatMessages,
      exploreChatMessages, setExploreChatMessages,
    }}>
      {children}
    </AppContext.Provider>
  );
};
