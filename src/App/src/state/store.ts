import { configureStore } from "@reduxjs/toolkit";
import appReducer from "./slices/appSlice";
import chatReducer from "./slices/chatSlice";
import citationReducer from "./slices/citationSlice";
import chatHistoryReducer from "./slices/chatHistorySlice";
import dashboardReducer from "./slices/dashboardSlice";

export const store = configureStore({
  reducer: {
    app: appReducer,
    dashboards: dashboardReducer,
    chat: chatReducer,
    citation: citationReducer,
    chatHistory: chatHistoryReducer,
  },
  devTools: import.meta.env.MODE !== "production",
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
