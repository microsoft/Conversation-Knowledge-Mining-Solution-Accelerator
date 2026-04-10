/**
 * Pre-defined, memoization-friendly selectors.
 *
 * Each selector accesses the **narrowest** slice of state a component
 * needs so React-Redux only triggers a re-render when that specific
 * value changes — never when an unrelated sibling field mutates.
 *
 * Usage:
 *   import { selectSelectedFilters } from "../store/selectors";
 *   const selectedFilters = useAppSelector(selectSelectedFilters);
 */

import type { RootState } from "./store";

// ── dashboards ──────────────────────────────────────────────

export const selectSelectedFilters = (s: RootState) =>
  s.dashboards.selectedFilters;

export const selectFiltersMeta = (s: RootState) =>
  s.dashboards.filtersMeta;

export const selectCharts = (s: RootState) =>
  s.dashboards.charts;

export const selectFetchingCharts = (s: RootState) =>
  s.dashboards.fetchingCharts;

export const selectFetchingFilters = (s: RootState) =>
  s.dashboards.fetchingFilters;

export const selectFiltersMetaFetched = (s: RootState) =>
  s.dashboards.filtersMetaFetched;

export const selectInitialChartsDataFetched = (s: RootState) =>
  s.dashboards.initialChartsDataFetched;

// ── chat ────────────────────────────────────────────────────

export const selectUserMessage = (s: RootState) =>
  s.chat.userMessage;

export const selectGeneratingResponse = (s: RootState) =>
  s.chat.generatingResponse;

export const selectMessages = (s: RootState) =>
  s.chat.messages;

export const selectIsStreamingInProgress = (s: RootState) =>
  s.chat.isStreamingInProgress;

// ── citation ────────────────────────────────────────────────

export const selectShowCitation = (s: RootState) =>
  s.citation.showCitation;

export const selectActiveCitation = (s: RootState) =>
  s.citation.activeCitation;

export const selectCurrentConversationIdForCitation = (s: RootState) =>
  s.citation.currentConversationIdForCitation;

// ── chatHistory ─────────────────────────────────────────────

export const selectChatHistoryList = (s: RootState) =>
  s.chatHistory.list;

export const selectFetchingConversations = (s: RootState) =>
  s.chatHistory.fetchingConversations;

export const selectIsFetchingConvMessages = (s: RootState) =>
  s.chatHistory.isFetchingConvMessages;

export const selectIsHistoryUpdateAPIPending = (s: RootState) =>
  s.chatHistory.isHistoryUpdateAPIPending;

// ── app ─────────────────────────────────────────────────────

export const selectAppConfig = (s: RootState) =>
  s.app.config.appConfig;

export const selectLayoutConfig = (s: RootState) =>
  s.app.config;

export const selectLayoutCharts = (s: RootState) =>
  s.app.config.charts;

export const selectShowAppSpinner = (s: RootState) =>
  s.app.showAppSpinner;

export const selectSelectedConversationId = (s: RootState) =>
  s.app.selectedConversationId;

export const selectGeneratedConversationId = (s: RootState) =>
  s.app.generatedConversationId;
