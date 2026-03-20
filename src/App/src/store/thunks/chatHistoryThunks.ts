/**
 * Async thunks for chat-history operations.
 *
 * Each thunk encapsulates the API call and lets slices react to
 * `pending` / `fulfilled` / `rejected` lifecycle via `extraReducers`,
 * eliminating multi-step dispatch sequences from components.
 */

import { createAsyncThunk } from "@reduxjs/toolkit";
import type { RootState } from "../store";
import type { ChatMessage, Conversation } from "../../types/AppTypes";
import {
  historyList,
  historyRead,
  historyDelete,
  historyDeleteAll,
  historyRename,
} from "../../api/api";

// ──────────────────────────────────────────────
//  fetchChatHistory
// ──────────────────────────────────────────────

export const fetchChatHistory = createAsyncThunk<
  Conversation[] | null,
  number
>("chatHistory/fetchChatHistory", async (offset) => {
  return await historyList(offset);
});

// ──────────────────────────────────────────────
//  loadConversation
// ──────────────────────────────────────────────

export const loadConversation = createAsyncThunk<
  { id: string; messages: ChatMessage[] },
  string
>("chatHistory/loadConversation", async (convId) => {
  const messages = await historyRead(convId);
  return { id: convId, messages };
});

// ──────────────────────────────────────────────
//  deleteConversation
// ──────────────────────────────────────────────

export const deleteConversation = createAsyncThunk<
  { convId: string; wasSelected: boolean },
  string,
  { state: RootState; rejectValue: string }
>(
  "chatHistory/deleteConversation",
  async (convId, { getState, rejectWithValue }) => {
    const response = await historyDelete(convId);
    if (!response.ok) {
      return rejectWithValue("Failed to delete conversation");
    }
    const { app } = getState();
    return {
      convId,
      wasSelected: convId === app.selectedConversationId,
    };
  }
);

// ──────────────────────────────────────────────
//  clearAllChatHistory
// ──────────────────────────────────────────────

export const clearAllChatHistory = createAsyncThunk<
  void,
  void,
  { rejectValue: string }
>("chatHistory/clearAllChatHistory", async (_, { rejectWithValue }) => {
  const response = await historyDeleteAll();
  if (!response.ok) {
    return rejectWithValue("Failed to clear chat history");
  }
});

// ──────────────────────────────────────────────
//  renameConversation
// ──────────────────────────────────────────────

export const renameConversation = createAsyncThunk<
  { convId: string; title: string },
  { convId: string; title: string },
  { rejectValue: string }
>(
  "chatHistory/renameConversation",
  async ({ convId, title }, { rejectWithValue }) => {
    const response = await historyRename(convId, title);
    if (!response.ok) {
      return rejectWithValue("Failed to rename conversation");
    }
    return { convId, title };
  }
);
