import {
  type Dispatch,
  type SetStateAction,
  useCallback,
  useEffect,
  useRef,
} from "react";
import {
  callConversationApi,
  historyUpdate,
} from "../api/api";
import { generateUUIDv4 } from "../configs/Utils";
import { useAppDispatch, useAppSelector } from "../state/hooks";
import {
  appendMessages,
  resetChatState,
  setGeneratingResponse,
  setStreamingInProgress,
  setUserMessage,
  updateMessageById,
} from "../state/slices/chatSlice";
import { hideCitation } from "../state/slices/citationSlice";
import {
  addConversationToHistory,
  setHistoryUpdateApiPending,
} from "../state/slices/chatHistorySlice";
import {
  setSelectedConversationId,
  startNewConversation,
} from "../state/slices/appSlice";
import {
  type ChatMessage,
  type Conversation,
  type ConversationRequest,
  type ParsedChunk,
} from "../types/AppTypes";
import { hasChartContent, parseChartContent } from "../utils/chartUtils";
import { isChartQuery } from "../utils/messageUtils";

type UseChatApiOptions = {
  scrollChatToBottom: () => void;
  setIsChartLoading: Dispatch<SetStateAction<boolean>>;
  isChartDisplayDefault: boolean;
};

const ASSISTANT = "assistant";
const ERROR = "error";
const USER = "user";

const getErrorMessage = (errorLine: string) => {
  try {
    const parsedError = JSON.parse(errorLine);
    return parsedError.error ===
      "Attempted to access streaming response content, without having called `read()`."
      ? "An error occurred. Please try again later."
      : parsedError.error;
  } catch {
    return errorLine;
  }
};

export const useChatApi = ({
  scrollChatToBottom,
  setIsChartLoading,
  isChartDisplayDefault,
}: UseChatApiOptions) => {
  const dispatch = useAppDispatch();
  const generatingResponse = useAppSelector(
    (state) => state.chat.generatingResponse
  );
  const isStreamingInProgress = useAppSelector(
    (state) => state.chat.isStreamingInProgress
  );
  const selectedConversationId = useAppSelector(
    (state) => state.app.selectedConversationId
  );
  const generatedConversationId = useAppSelector(
    (state) => state.app.generatedConversationId
  );
  const abortControllersRef = useRef<AbortController[]>([]);

  useEffect(() => {
    if (generatingResponse || isStreamingInProgress) {
      const chatAPISignal = abortControllersRef.current.shift();
      chatAPISignal?.abort(
        "Chat Aborted due to switch to other conversation while generating"
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedConversationId]);

  const readStreamingResponse = useCallback(
    async (
      response: Response,
      handlers: {
        onToolDelta?: (content: string) => void;
        onAssistantDelta?: (content: string) => void;
      }
    ) => {
      const reader = response.body?.getReader();

      if (!reader) {
        return {
          accumulatedContent: "",
          errorLine: "",
          hasError: false,
        };
      }

      let accumulatedContent = "";
      let errorLine = "";
      let hasError = false;
      let lineBuffer = "";
      const decoder = new TextDecoder("utf-8");

      const processLine = (rawLine: string) => {
        const line = rawLine.trim();
        if (!line || line === "{}") {
          return;
        }

        try {
          const parsedChunk: ParsedChunk = JSON.parse(line);
          if (parsedChunk?.error) {
            hasError = true;
            errorLine = line;
            return;
          }

          const delta = parsedChunk?.choices?.[0]?.delta;
          if (delta?.role === "tool" && delta.content) {
            handlers.onToolDelta?.(delta.content);
          }

          if (delta?.role === "assistant" && delta.content) {
            accumulatedContent += delta.content;
            handlers.onAssistantDelta?.(accumulatedContent);
          }
        } catch {
          return;
        }
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        lineBuffer += decoder.decode(value, { stream: true });
        const lines = lineBuffer.split("\n");
        lineBuffer = lines.pop() ?? "";

        for (const rawLine of lines) {
          processLine(rawLine);
          if (hasError) {
            break;
          }
        }

        if (hasError) {
          break;
        }
      }

      // Flush any remaining decoded bytes and process a final non-newline-terminated NDJSON line.
      lineBuffer += decoder.decode();
      if (!hasError && lineBuffer.trim()) {
        processLine(lineBuffer);
      }

      return {
        accumulatedContent,
        errorLine,
        hasError,
      };
    },
    []
  );

  const handleChartResult = useCallback(
    (
      chartResponse: unknown,
      streamMessage: ChatMessage,
      newMessage: ChatMessage,
      suppressErrors = false
    ): ChatMessage[] => {
      if (hasChartContent(chartResponse)) {
        const chartMessage: ChatMessage = {
          ...streamMessage,
          content: chartResponse,
          role: ASSISTANT,
        };

        dispatch(updateMessageById(chartMessage));
        scrollChatToBottom();
        return [newMessage, chartMessage];
      }

      if (suppressErrors) {
        return [];
      }

      const errorMessage: ChatMessage = {
        ...streamMessage,
        content:
          typeof chartResponse === "string"
            ? chartResponse
            : JSON.stringify(chartResponse),
        role: ERROR,
      };

      dispatch(updateMessageById(errorMessage));
      scrollChatToBottom();
      return [newMessage, errorMessage];
    },
    [dispatch, scrollChatToBottom]
  );

  const saveConversation = useCallback(
    async (
      newMessages: ChatMessage[],
      conversationId: string,
      requestType = "Text"
    ) => {
      if (!conversationId || !newMessages.length) {
        return false;
      }

      const isNewConversation =
        requestType !== "graph" && !selectedConversationId;

      dispatch(setHistoryUpdateApiPending(true));

      try {
        const response = await historyUpdate(newMessages, conversationId);
        if (!response.ok) {
          throw new Error("Unable to persist the current conversation.");
        }

        const responseJson = await response.json();
        if (isNewConversation && responseJson?.success) {
          const newConversation: Conversation = {
            id: responseJson?.data?.conversation_id,
            title: responseJson?.data?.title,
            messages: [...newMessages],
            date: responseJson?.data?.date,
            updatedAt: responseJson?.data?.date,
          };

          dispatch(addConversationToHistory(newConversation));
          dispatch(setSelectedConversationId(responseJson?.data?.conversation_id));
        }

        return true;
      } catch {
        return false;
      } finally {
        dispatch(setGeneratingResponse(false));
        dispatch(setHistoryUpdateApiPending(false));
      }
    },
    [dispatch, selectedConversationId]
  );

  const makeChartRequest = useCallback(
    async (
      question: string,
      conversationId: string,
      isAutomatic = false
    ) => {
      if (generatingResponse || !question.trim()) {
        return;
      }

      const newMessage: ChatMessage = {
        id: generateUUIDv4(),
        role: USER,
        content: question,
        date: new Date().toISOString(),
      };

      if (!isAutomatic) {
        dispatch(setGeneratingResponse(true));
        scrollChatToBottom();
        dispatch(appendMessages([newMessage]));
        dispatch(setUserMessage(""));
      }

      const abortController = new AbortController();
      abortControllersRef.current.unshift(abortController);

      const request: ConversationRequest = {
        id: conversationId,
        query: question,
      };

      const streamMessage: ChatMessage = {
        id: generateUUIDv4(),
        date: new Date().toISOString(),
        role: ASSISTANT,
        content: "",
      };
      let updatedMessages: ChatMessage[] = [];

      try {
        const response = await callConversationApi(request, abortController.signal);
        const { accumulatedContent, errorLine, hasError } =
          await readStreamingResponse(response, {
            onAssistantDelta: () => undefined,
          });

        if (hasError) {
          const errorMessage: ChatMessage = {
            id: generateUUIDv4(),
            role: ERROR,
            content: getErrorMessage(errorLine),
            date: new Date().toISOString(),
          };

          updatedMessages = isAutomatic ? [] : [newMessage, errorMessage];
          if (!isAutomatic) {
            dispatch(appendMessages([errorMessage]));
            scrollChatToBottom();
          }
        } else {
          const chartResponse = parseChartContent(accumulatedContent);
          updatedMessages = handleChartResult(
            chartResponse,
            streamMessage,
            newMessage,
            isAutomatic
          );
        }

        if (!isAutomatic || updatedMessages.length > 0) {
          await saveConversation(updatedMessages, conversationId, "graph");
        }
      } catch (error) {
        if (abortController.signal.aborted && !isAutomatic) {
          const partialMessages = streamMessage.content
            ? [newMessage, streamMessage]
            : [newMessage];
          await saveConversation(partialMessages, conversationId, "graph");
        }

        if (!abortController.signal.aborted && !isAutomatic) {
          alert(
            error instanceof Error
              ? error.message
              : "An error occurred. Please try again."
          );
        }
      } finally {
        abortControllersRef.current = abortControllersRef.current.filter(
          (controller) => controller !== abortController
        );

        if (!isAutomatic) {
          dispatch(setGeneratingResponse(false));
        }

        dispatch(setStreamingInProgress(false));
        setIsChartLoading(false);
      }
    },
    [
      dispatch,
      generatingResponse,
      handleChartResult,
      readStreamingResponse,
      saveConversation,
      scrollChatToBottom,
      setIsChartLoading,
    ]
  );

  const sendMessage = useCallback(
    async (question: string) => {
      if (generatingResponse || !question.trim()) {
        return;
      }

      const conversationId = selectedConversationId || generatedConversationId;
      const requestType = isChartQuery(question) ? "graph" : "Text";
      const newMessage: ChatMessage = {
        id: generateUUIDv4(),
        role: USER,
        content: question,
        date: new Date().toISOString(),
      };

      dispatch(setGeneratingResponse(true));
      scrollChatToBottom();
      dispatch(appendMessages([newMessage]));
      dispatch(setUserMessage(""));

      const abortController = new AbortController();
      abortControllersRef.current.unshift(abortController);

      const request: ConversationRequest = {
        id: conversationId,
        query: question,
      };

      const streamMessage: ChatMessage = {
        id: generateUUIDv4(),
        date: new Date().toISOString(),
        role: ASSISTANT,
        content: "",
        citations: "",
      };
      let updatedMessages: ChatMessage[] = [];

      try {
        const response = await callConversationApi(request, abortController.signal);
        const isChart = isChartQuery(question);
        const { accumulatedContent, errorLine, hasError } =
          await readStreamingResponse(response, {
            onToolDelta: (content) => {
              streamMessage.citations = content;
              if (!isChart) {
                dispatch(setStreamingInProgress(true));
                dispatch(updateMessageById({ ...streamMessage }));
              }
            },
            onAssistantDelta: (content) => {
              if (!isChart) {
                streamMessage.content = content;
                streamMessage.role = ASSISTANT;
                dispatch(setStreamingInProgress(true));
                dispatch(updateMessageById({ ...streamMessage }));
                scrollChatToBottom();
              }
            },
          });

        if (hasError) {
          const errorMessage: ChatMessage = {
            id: generateUUIDv4(),
            role: ERROR,
            content: getErrorMessage(errorLine),
            date: new Date().toISOString(),
          };

          updatedMessages = [newMessage, errorMessage];
          dispatch(appendMessages([errorMessage]));
          scrollChatToBottom();
        } else if (isChart) {
          const chartResponse = parseChartContent(accumulatedContent);
          updatedMessages = handleChartResult(chartResponse, streamMessage, newMessage);
        } else {
          updatedMessages = [
            newMessage,
            {
              ...streamMessage,
              content: accumulatedContent || streamMessage.content,
              role: ASSISTANT,
            },
          ];
        }

        if (updatedMessages[updatedMessages.length - 1]?.role !== ERROR) {
          const didSave = await saveConversation(
            updatedMessages,
            conversationId,
            requestType
          );

          if (
            didSave &&
            requestType !== "graph" &&
            updatedMessages[updatedMessages.length - 1]?.role !== ERROR &&
            isChartDisplayDefault
          ) {
            setIsChartLoading(true);
            setTimeout(() => {
              void makeChartRequest(
                "show in a graph by default",
                conversationId,
                true
              );
            }, 5000);
          }
        }
      } catch (error) {
        if (abortController.signal.aborted) {
          const partialMessages = streamMessage.content
            ? [newMessage, streamMessage]
            : [newMessage];
          await saveConversation(partialMessages, conversationId, "error");
        }

        if (!abortController.signal.aborted) {
          alert(
            error instanceof Error
              ? error.message
              : "An error occurred. Please try again."
          );
        }
      } finally {
        abortControllersRef.current = abortControllersRef.current.filter(
          (controller) => controller !== abortController
        );

        dispatch(setGeneratingResponse(false));
        dispatch(setStreamingInProgress(false));
      }
    },
    [
      dispatch,
      generatedConversationId,
      generatingResponse,
      handleChartResult,
      isChartDisplayDefault,
      makeChartRequest,
      readStreamingResponse,
      saveConversation,
      scrollChatToBottom,
      selectedConversationId,
      setIsChartLoading,
    ]
  );

  const startNewChat = useCallback(() => {
    dispatch(resetChatState());
    dispatch(startNewConversation());
    dispatch(hideCitation());
  }, [dispatch]);

  return {
    sendMessage,
    startNewChat,
  };
};
