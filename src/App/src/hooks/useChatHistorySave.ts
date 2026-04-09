import { useCallback } from "react";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import type { ChatMessage, Conversation } from "../types/AppTypes";
import { historyUpdate } from "../api/api";
import { setGeneratingResponse } from "../store/slices/chatSlice";
import { setHistoryUpdateAPIPending, addNewConversation } from "../store/slices/chatHistorySlice";
import { setSelectedConversationId } from "../store/slices/appSlice";

/**
 * Encapsulates the "save messages to DB" side-effect that runs
 * after every successful (or aborted) chat API call.
 *
 * Returns a stable `saveToDB` function whose identity only changes
 * when the Redux-derived dependencies change.
 */
export function useChatHistorySave() {
  const dispatch = useAppDispatch();
  const messages = useAppSelector((s) => s.chat.messages);
  const selectedConversationId = useAppSelector((s) => s.app.selectedConversationId);

  const saveToDB = useCallback(
    async (newMessages: ChatMessage[], convId: string, reqType: string = "Text") => {
      if (!convId || !newMessages.length) {
        return;
      }

      const hasAssistantMessage = newMessages.some(
        (msg) => msg.role === "assistant" && Boolean(msg.content)
      );

      if (!hasAssistantMessage) {
        dispatch(setGeneratingResponse(false));
        dispatch(setHistoryUpdateAPIPending(false));
        return;
      }

      const isNewConversation = reqType !== "graph" ? !selectedConversationId : false;
      dispatch(setHistoryUpdateAPIPending(true));

      await historyUpdate(newMessages, convId)
        .then(async (res) => {
          if (!res.ok) {
            if (!messages) {
              const err: Error = {
                ...new Error(),
                message: "Failure fetching current chat state.",
              };
              throw err;
            }
          }

          const responseJson = await res.json();
          if (isNewConversation && responseJson?.success) {
            const newConversation: Conversation = {
              id: responseJson?.data?.conversation_id,
              title: responseJson?.data?.title,
              messages,
              date: responseJson?.data?.date,
              updatedAt: responseJson?.data?.date,
            };
            dispatch(addNewConversation(newConversation));
            dispatch(setSelectedConversationId(responseJson?.data?.conversation_id));
          }
          dispatch(setHistoryUpdateAPIPending(false));
          return res as Response;
        })
        .catch(() => {
          console.error("Error: while saving data");
        })
        .finally(() => {
          dispatch(setGeneratingResponse(false));
          dispatch(setHistoryUpdateAPIPending(false));
        });
    },
    [dispatch, messages, selectedConversationId]
  );

  return { saveToDB };
}
