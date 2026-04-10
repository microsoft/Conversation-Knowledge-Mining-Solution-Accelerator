import { configureStore } from "@reduxjs/toolkit";
import dashboardsReducer from "./slices/dashboardsSlice";
import chatReducer from "./slices/chatSlice";
import citationReducer from "./slices/citationSlice";
import chatHistoryReducer from "./slices/chatHistorySlice";
import appReducer from "./slices/appSlice";

export const store = configureStore({
  reducer: {
    dashboards: dashboardsReducer,
    chat: chatReducer,
    citation: citationReducer,
    chatHistory: chatHistoryReducer,
    app: appReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
