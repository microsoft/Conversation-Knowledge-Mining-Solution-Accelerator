import React, { createContext, useContext, useState, ReactNode } from "react";

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

export const AppStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [insights, setInsights] = useState<any | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [exploreChatMessages, setExploreChatMessages] = useState<ChatMessage[]>([]);

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
