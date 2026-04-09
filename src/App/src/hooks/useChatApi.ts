import { useCallback, useRef, useState, type RefObject } from "react";
import { useAppDispatch, useAppSelector } from "../store/hooks";
import type {
  ChatMessage,
  ChartDataResponse,
  ConversationRequest,
  ParsedChunk,
  Citation,
} from "../types/AppTypes";
import { callConversationApi } from "../api/api";
import { generateUUIDv4 } from "../utils/messageUtils";
import { safeParse } from "../utils/jsonUtils";
import {
  extractAnswerAndCitations,
  parseChartContent,
} from "../utils/chatParsingUtils";
import {
  setGeneratingResponse,
  appendMessages,
  setUserMessage,
  updateMessageById,
  setStreamingFlag,
} from "../store/slices/chatSlice";

const [ASSISTANT, , ERROR] = ["assistant", "tool", "error"];

interface UseChatApiOptions {
  /** Scroll the chat viewport to the bottom */
  scrollToBottom: (behavior?: ScrollBehavior) => void;
  /** Persist messages to the database */
  saveToDB: (msgs: ChatMessage[], convId: string, reqType?: string) => Promise<void>;
  /** Ref to the textarea so we can refocus after send */
  questionInputRef: RefObject<HTMLTextAreaElement>;
  /** Whether to auto-request a chart after every successful text response */
  isChartDisplayDefault: boolean;
}

/**
 * Houses the two primary chat API flows:
 *  • `makeApiRequestWithCosmosDB` – text / streaming chat
 *  • `makeApiRequestForChart`     – chart-specific request
 *
 * All abort-controller bookkeeping is internal.
 */
export function useChatApi({
  scrollToBottom,
  saveToDB,
  questionInputRef,
  isChartDisplayDefault,
}: UseChatApiOptions) {
  const dispatch = useAppDispatch();
  const userMessage = useAppSelector((s) => s.chat.userMessage);
  const generatingResponse = useAppSelector((s) => s.chat.generatingResponse);
  const messages = useAppSelector((s) => s.chat.messages);

  const abortFuncs = useRef<AbortController[]>([]);
  const [isChartLoading, setIsChartLoading] = useState(false);

  // ──────────────────────────────────────────────
  //  Helpers
  // ──────────────────────────────────────────────
  const isChartQuery = useCallback((query: string) => {
    const chartKeywords = ["chart", "graph", "visualize", "plot"];
    return chartKeywords.some((kw) => query.toLowerCase().includes(kw));
  }, []);

  const parseCitationFromMessage = useCallback((message: any): Citation[] => {
    if (Array.isArray(message)) {
      return message as Citation[];
    }
    if (message && typeof message === "object") {
      return Array.isArray(message.citations)
        ? (message.citations as Citation[])
        : ([] as Citation[]);
    }
    if (typeof message !== "string") {
      return [] as Citation[];
    }
    const trimmedMessage = message.trim();
    if (!trimmedMessage) {
      return [] as Citation[];
    }
    if (trimmedMessage.startsWith("{")) {
      const toolMessage = safeParse<{ citations?: Citation[] }>(trimmedMessage, {});
      return toolMessage.citations ?? ([] as Citation[]);
    }
    if (trimmedMessage.startsWith("[")) {
      return safeParse<Citation[]>(trimmedMessage, []);
    }
    // Legacy fragment format: missing leading `{`
    const toolMessage = safeParse<{ citations?: Citation[] }>(
      "{" + trimmedMessage,
      {}
    );
    return toolMessage.citations ?? ([] as Citation[]);
  }, []);

  // ──────────────────────────────────────────────
  //  makeApiRequestForChart
  // ──────────────────────────────────────────────
  const makeApiRequestForChart = useCallback(
    async (question: string, conversationId: string, _lrg: string) => {
      if (generatingResponse || !question.trim()) {
        setIsChartLoading(false);
        return;
      }

      const newMessage: ChatMessage = {
        id: generateUUIDv4(),
        role: "user",
        content: question,
        date: new Date().toISOString(),
      };
      dispatch(setGeneratingResponse(true));
      scrollToBottom();
      dispatch(appendMessages([newMessage]));
      dispatch(setUserMessage(questionInputRef?.current?.value || ""));

      const abortController = new AbortController();
      abortFuncs.current.unshift(abortController);

      const request: ConversationRequest = { id: conversationId, query: question };
      const streamMessage: ChatMessage = {
        id: generateUUIDv4(),
        date: new Date().toISOString(),
        role: ASSISTANT,
        content: "",
      };
      let updatedMessages: ChatMessage[] = [];

      try {
        const response = await callConversationApi(request, abortController.signal);

        if (response?.body) {
          let isChartResponseReceived = false;
          const reader = response.body.getReader();
          let runningText = "";
          let hasError = false;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const text = new TextDecoder("utf-8").decode(value);
            const textObj = safeParse<any>(text, null);
            if (textObj?.object?.data) {
              runningText = text;
              isChartResponseReceived = true;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = text;
            }
          }

          if (hasError) {
            const errorMsg = safeParse<any>(runningText, {}).error;
            const errorMessage: ChatMessage = {
              id: generateUUIDv4(),
              role: ERROR,
              content: errorMsg,
              date: new Date().toISOString(),
            };
            updatedMessages = [newMessage, errorMessage];
            dispatch(appendMessages([errorMessage]));
            scrollToBottom();
          } else if (isChartQuery(question)) {
            const parsedChartResponse = safeParse<any>(runningText, null);
            if (parsedChartResponse) {
              if (
                "object" in parsedChartResponse &&
                parsedChartResponse?.object?.type &&
                parsedChartResponse?.object?.data
              ) {
                try {
                  const chartMessage: ChatMessage = {
                    id: generateUUIDv4(),
                    role: ASSISTANT,
                    content: parsedChartResponse.object as unknown as ChartDataResponse,
                    date: new Date().toISOString(),
                  };
                  updatedMessages = [newMessage, chartMessage];
                  dispatch(appendMessages([chartMessage]));
                  scrollToBottom();
                } catch {
                  const chartMessage: ChatMessage = {
                    id: generateUUIDv4(),
                    role: ASSISTANT,
                    content: "Error while generating Chart.",
                    date: new Date().toISOString(),
                  };
                  updatedMessages = [newMessage, chartMessage];
                  dispatch(appendMessages([chartMessage]));
                  scrollToBottom();
                }
              } else if (parsedChartResponse.error) {
                const errorMsg =
                  parsedChartResponse.error || parsedChartResponse?.object?.message;
                const errorMessage: ChatMessage = {
                  id: generateUUIDv4(),
                  role: ERROR,
                  content: errorMsg,
                  date: new Date().toISOString(),
                };
                updatedMessages = [...messages, newMessage, errorMessage];
                dispatch(appendMessages([errorMessage]));
                scrollToBottom();
              }
            }
          }
        }
        saveToDB(updatedMessages, conversationId, "graph");
      } catch (e) {
        if (abortController.signal.aborted) {
          updatedMessages = streamMessage.content
            ? [newMessage, streamMessage]
            : [newMessage];
          saveToDB(updatedMessages, conversationId, "graph");
        }
        if (!abortController.signal.aborted) {
          if (e instanceof Error) alert(e.message);
          else
            alert(
              "An error occurred. Please try again. If the problem persists, please contact the site administrator."
            );
        }
      } finally {
        dispatch(setGeneratingResponse(false));
        dispatch(setStreamingFlag(false));
        setIsChartLoading(false);
        const idx = abortFuncs.current.indexOf(abortController);
        if (idx > -1) abortFuncs.current.splice(idx, 1);
      }
    },
    [
      dispatch,
      generatingResponse,
      messages,
      isChartQuery,
      saveToDB,
      scrollToBottom,
      questionInputRef,
    ]
  );

  // ──────────────────────────────────────────────
  //  makeApiRequestWithCosmosDB
  // ──────────────────────────────────────────────
  const makeApiRequestWithCosmosDB = useCallback(
    async (question: string, conversationId: string) => {
      if (generatingResponse || !question.trim()) return;

      const isChatReq = isChartQuery(userMessage) ? "graph" : "Text";
      const newMessage: ChatMessage = {
        id: generateUUIDv4(),
        role: "user",
        content: question,
        date: new Date().toISOString(),
      };
      dispatch(setGeneratingResponse(true));
      scrollToBottom();
      dispatch(appendMessages([newMessage]));
      dispatch(setUserMessage(""));

      const abortController = new AbortController();
      abortFuncs.current.unshift(abortController);

      const request: ConversationRequest = { id: conversationId, query: question };
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

        if (response?.body) {
          let isChartResponseReceived = false;
          const reader = response.body.getReader();
          const decoder = new TextDecoder("utf-8");
          let runningText = "";
          let hasError = false;
          let lineBuffer = "";
          let chartResponseBuffer = "";

          const processNdjsonText = (rawText: string) => {
            const trimmedText = rawText.trim();
            if (trimmedText === "" || trimmedText === "{}") {
              return;
            }

            const parsed = safeParse<ParsedChunk | null>(trimmedText, null);
            if (!parsed) {
              return;
            }

            if (parsed?.error && !hasError) {
              hasError = true;
              runningText = parsed.error;
              return;
            }

            if (isChartQuery(userMessage) && !hasError) {
              runningText += trimmedText;
              return;
            }

            if (typeof parsed === "object" && !hasError) {
              const delta = parsed?.choices?.[0]?.delta;

              if (delta?.role === "tool" && delta?.content) {
                streamMessage.citations = delta.content;
                dispatch(updateMessageById({ ...streamMessage }));
                return;
              }

              if (delta?.content) {
                runningText += delta.content;
                streamMessage.content = runningText;
                streamMessage.role = delta.role || ASSISTANT;
                dispatch(updateMessageById({ ...streamMessage }));
                scrollToBottom();
                return;
              }

              const responseContent =
                parsed?.choices?.[0]?.messages?.[0]?.content;

              if (responseContent) {
                const extracted = extractAnswerAndCitations(
                  responseContent,
                  parsed?.choices?.[0]?.messages?.[0]?.role || ASSISTANT
                );

                streamMessage.content = extracted.answer || "";
                streamMessage.role = extracted.role;
                streamMessage.citations = extracted.citations;
                dispatch(updateMessageById({ ...streamMessage }));
                scrollToBottom();
              }
            }
          };

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value, { stream: true });
            if (!text) continue;

            chartResponseBuffer += text;

            const textObj =
              safeParse<any>(chartResponseBuffer, null) ??
              safeParse<any>(text, null);

            if (textObj?.object?.data) {
              runningText = chartResponseBuffer;
              isChartResponseReceived = true;
            }
            if (textObj?.object?.message) {
              runningText = chartResponseBuffer;
              isChartResponseReceived = true;
            }
            if (textObj?.error) {
              hasError = true;
              runningText = chartResponseBuffer;
            }

            if (!isChartResponseReceived) {
              lineBuffer += text;
              const lines = lineBuffer.split("\n");
              lineBuffer = lines.pop() ?? "";

              lines.forEach((line) => {
                processNdjsonText(line);
              });

              if (hasError) {
                break;
              }
            }
          }

          const finalText = decoder.decode();
          if (finalText) {
            chartResponseBuffer += finalText;
            if (!isChartResponseReceived) {
              lineBuffer += finalText;
            }
          }

          const finalChartObj = safeParse<any>(chartResponseBuffer, null);
          if (finalChartObj?.object?.data) {
            runningText = chartResponseBuffer;
            isChartResponseReceived = true;
          }
          if (finalChartObj?.object?.message) {
            runningText = chartResponseBuffer;
            isChartResponseReceived = true;
          }
          if (finalChartObj?.error && !hasError) {
            hasError = true;
            runningText = chartResponseBuffer;
          }
          if (!isChartResponseReceived && !hasError) {
            processNdjsonText(lineBuffer);
          }

          // END OF STREAMING
          if (hasError) {
            const parsedRunning = safeParse<any>(runningText, {});
            const errorMsg =
              parsedRunning.error ===
              "Attempted to access streaming response content, without having called `read()`."
                ? "An error occurred. Please try again later."
                : parsedRunning.error;

            const errorMessage: ChatMessage = {
              id: generateUUIDv4(),
              role: ERROR,
              content: errorMsg,
              date: new Date().toISOString(),
            };
            updatedMessages = [newMessage, errorMessage];
            dispatch(appendMessages([errorMessage]));
            scrollToBottom();
          } else if (isChartQuery(userMessage)) {
            const chartResult = parseChartContent(runningText);

            if (chartResult.kind === "chart" && chartResult.chartData) {
              const chartMessage: ChatMessage = {
                id: generateUUIDv4(),
                role: ASSISTANT,
                content: chartResult.chartData as unknown as ChartDataResponse,
                date: new Date().toISOString(),
              };
              updatedMessages = [newMessage, chartMessage];
              dispatch(appendMessages([chartMessage]));
              scrollToBottom();
            } else if (chartResult.kind === "error") {
              const errorMessage: ChatMessage = {
                id: generateUUIDv4(),
                role: ERROR,
                content: chartResult.errorMessage ?? "Error while generating Chart.",
                date: new Date().toISOString(),
              };
              updatedMessages = [newMessage, errorMessage];
              dispatch(appendMessages([errorMessage]));
              scrollToBottom();
            }
          } else if (!isChartResponseReceived) {
            updatedMessages = [newMessage, streamMessage];
          }
        }

        if (updatedMessages[updatedMessages.length - 1]?.role !== "error") {
          // Fire chart default + save
          if (
            isChatReq !== "graph" &&
            updatedMessages[updatedMessages.length - 1]?.role !== ERROR &&
            isChartDisplayDefault
          ) {
            const preservedUserMessage = userMessage;
            const chartSourceMessage = updatedMessages[updatedMessages.length - 1]
              ?.content as string;
            setIsChartLoading(true);
            setTimeout(() => {
              void makeApiRequestForChart(
                "",
                conversationId,
                chartSourceMessage
              )
                .catch(() => {
                  // Automatic chart generation should not surface errors to the user.
                })
                .finally(() => {
                  dispatch(setUserMessage(preservedUserMessage));
                  dispatch(setGeneratingResponse(false));
                  dispatch(setStreamingFlag(false));
                });
            }, 5000);
          }
          saveToDB(updatedMessages, conversationId, isChatReq);
        }
      } catch (e) {
        if (abortController.signal.aborted) {
          updatedMessages = streamMessage.content
            ? [newMessage, streamMessage]
            : [newMessage];
          saveToDB(updatedMessages, conversationId, "error");
        }
        if (!abortController.signal.aborted) {
          if (e instanceof Error) alert(e.message);
          else
            alert(
              "An error occurred. Please try again. If the problem persists, please contact the site administrator."
            );
        }
      } finally {
        dispatch(setGeneratingResponse(false));
        dispatch(setStreamingFlag(false));
        const idx = abortFuncs.current.indexOf(abortController);
        if (idx > -1) abortFuncs.current.splice(idx, 1);
      }
    },
    [
      dispatch,
      generatingResponse,
      userMessage,
      isChartQuery,
      isChartDisplayDefault,
      makeApiRequestForChart,
      saveToDB,
      scrollToBottom,
    ]
  );

  return {
    makeApiRequestWithCosmosDB,
    makeApiRequestForChart,
    isChartLoading,
    isChartQuery,
    parseCitationFromMessage,
    abortFuncs,
  } as const;
}
