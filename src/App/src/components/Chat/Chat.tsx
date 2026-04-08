import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Textarea,
  Subtitle2,
  Body1,
} from "@fluentui/react-components";
import { DefaultButton, Spinner, SpinnerSize } from "@fluentui/react";
import { ChatAdd24Regular } from "@fluentui/react-icons";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";

import { getIsChartDisplayDefault } from "../../api/api";
import ChatChart from "../ChatChart/ChatChart";
import Citations from "../Citations/Citations";
import { useAutoScroll, useChatApi, useChatHistorySave, useTextareaAutoResize } from "../../hooks";
import { useAppDispatch, useAppSelector } from "../../store/hooks";
import { newConversationStart } from "../../store/slices/appSlice";
import { setUserMessage, clearMessages } from "../../store/slices/chatSlice";
import { updateCitation } from "../../store/slices/citationSlice";
import type { ChartDataResponse } from "../../types/AppTypes";

type ChatProps = {
  onHandlePanelStates: (name: string) => void;
  panels: Record<string, string>;
  panelShowStates: Record<string, boolean>;
};

const Chat: React.FC<ChatProps> = ({
  onHandlePanelStates,
  panelShowStates,
  panels,
}) => {
  const dispatch = useAppDispatch();
  const userMessage = useAppSelector((s) => s.chat.userMessage);
  const generatingResponse = useAppSelector((s) => s.chat.generatingResponse);
  const messages = useAppSelector((s) => s.chat.messages);
  const isStreamingInProgress = useAppSelector((s) => s.chat.isStreamingInProgress);
  const selectedConversationId = useAppSelector((s) => s.app.selectedConversationId);
  const generatedConversationId = useAppSelector((s) => s.app.generatedConversationId);
  const isFetchingConvMessages = useAppSelector((s) => s.chatHistory.isFetchingConvMessages);
  const isHistoryUpdateAPIPending = useAppSelector((s) => s.chatHistory.isHistoryUpdateAPIPending);

  const questionInputRef = useRef<HTMLTextAreaElement>(null);
  const [isChartDisplayDefault, setIsChartDisplayDefault] = useState(false);

  // ── Custom hooks ──────────────────────────────
  const { scrollRef, scrollToBottom } = useAutoScroll([generatingResponse]);
  const { saveToDB } = useChatHistorySave();
  const {
    makeApiRequestWithCosmosDB,
    isChartLoading,
    parseCitationFromMessage,
    abortFuncs,
  } = useChatApi({
    scrollToBottom,
    saveToDB,
    questionInputRef,
    isChartDisplayDefault,
  });

  useTextareaAutoResize(questionInputRef, userMessage);

  // ── Derived / memoised values ─────────────────
  const isInputDisabled = useMemo(
    () => generatingResponse || isHistoryUpdateAPIPending,
    [generatingResponse, isHistoryUpdateAPIPending]
  );

  const isSendDisabled = useMemo(
    () => generatingResponse || !userMessage.trim() || isHistoryUpdateAPIPending,
    [generatingResponse, userMessage, isHistoryUpdateAPIPending]
  );

  const showLoadingIndicator = useMemo(
    () => (generatingResponse && !isStreamingInProgress) || isChartLoading,
    [generatingResponse, isStreamingInProgress, isChartLoading]
  );

  // ── Side-effects ──────────────────────────────
  useEffect(() => {
    try {
      const fetchFlag = async () => {
        const cfg = await getIsChartDisplayDefault();
        setIsChartDisplayDefault(cfg.isChartDisplayDefault);
      };
      void fetchFlag();
    } catch (error) {
      console.error("Failed to fetch isChartDisplayDefault flag", error);
    }
  }, []);

  useEffect(() => {
    if (generatingResponse || isStreamingInProgress) {
      const chatAPISignal = abortFuncs.current.shift();
      if (chatAPISignal) {
        chatAPISignal.abort(
          "Chat aborted due to switch to other conversation while generating"
        );
      }
    }
  }, [selectedConversationId, abortFuncs, generatingResponse, isStreamingInProgress]);
  useEffect(() => {
    if (!isFetchingConvMessages) {
      scrollToBottom("auto");
    }
  }, [isFetchingConvMessages, scrollToBottom]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const conversationId = selectedConversationId || generatedConversationId;
        if (userMessage.trim()) {
          void makeApiRequestWithCosmosDB(userMessage, conversationId);
        }
        questionInputRef.current?.focus();
      }
    },
    [
      selectedConversationId,
      generatedConversationId,
      userMessage,
      makeApiRequestWithCosmosDB,
    ]
  );

  const onClickSend = useCallback(() => {
    const conversationId = selectedConversationId || generatedConversationId;
    if (userMessage) {
      makeApiRequestWithCosmosDB(userMessage, conversationId);
    }
    questionInputRef?.current?.focus();
  }, [selectedConversationId, generatedConversationId, userMessage, makeApiRequestWithCosmosDB]);

  const setUserMessageValue = useCallback(
    (value: string) => {
      dispatch(setUserMessage(value));
    },
    [dispatch]
  );

  const onNewConversation = useCallback(() => {
    dispatch(newConversationStart());
    dispatch(clearMessages());
    dispatch(updateCitation({ activeCitation: null, showCitation: false }));
  }, [dispatch]);
  return (
    <div className="chat-container">
      <div className="chat-header">
        <Subtitle2>Chat</Subtitle2>
        <span>
          <Button
            appearance="outline"
            onClick={() => onHandlePanelStates(panels.CHATHISTORY)}
            className="hide-chat-history"
          >
            {`${panelShowStates?.[panels.CHATHISTORY] ? "Hide" : "Show"
              } Chat History`}
          </Button>
        </span>
      </div>
      <div className="chat-messages">
        {Boolean(isFetchingConvMessages) && (
          <div>
            <Spinner
              size={SpinnerSize.small}
              aria-label="Fetching Chat messages"
            />
          </div>
        )}
        {!Boolean(isFetchingConvMessages) &&
          messages.length === 0 && (
            <div className="initial-msg">
              {/* <SparkleRegular fontSize={32} /> */}
              <h2>✨</h2>
              <Subtitle2>Start Chatting</Subtitle2>
              <Body1 style={{ textAlign: "center" }}>
                You can ask questions around customers calls, call topics and
                call sentiments.
              </Body1>
            </div>
          )}
        {!Boolean(isFetchingConvMessages) &&
          messages.map((msg, index: number) => (
            <div key={index} className={`chat-message ${msg.role}`}>
              {(() => {
                 const isLastAssistantMessage =
                 msg.role === "assistant" && index === messages.length - 1;
                if ((msg.role === "user") && typeof msg.content === "string") {
                  if (msg.content == "show in a graph by default") return null;
                    return (
                      <div className="user-message">
                        <span>{msg.content}</span>
                      </div>
                    );

                }
                const chartContent = msg.content as ChartDataResponse;
                if (chartContent?.type && chartContent?.data) {
                  return (
                    <div className="assistant-message chart-message">
                      <ChatChart chartContent={chartContent} />
                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }
                if (typeof msg.content === "string") {
                  return (
                    <div className="assistant-message">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm, supersub]}
                        children={msg.content}
                      />
                     {/* Citation Loader: Show only while citations are fetching */}
                      {isLastAssistantMessage && generatingResponse ? (
                        <div className="typing-indicator">
                          <span className="dot"></span>
                          <span className="dot"></span>
                          <span className="dot"></span>
                        </div>
                      ) : (
                        <Citations
                            answer={{
                              answer: msg.content,
                              citations:
                                msg.role === "assistant" && msg.citations
                                  ? typeof msg.citations === "string"
                                    ? parseCitationFromMessage(msg.citations)
                                    : Array.isArray(msg.citations)
                                      ? msg.citations
                                      : []
                                  : [],
                            }}
                            index={index}
                          />
                      )}

                      <div className="answerDisclaimerContainer">
                        <span className="answerDisclaimer">
                          AI-generated content may be incorrect
                        </span>
                      </div>
                    </div>
                  );
                }
              })()}
            </div>
          ))}
        {showLoadingIndicator && (
          <div className="assistant-message loading-indicator">
            <div className="typing-indicator">
              <span className="generating-text">{isChartLoading ? "Generating chart if possible with the provided data" : "Generating answer"} </span>
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div data-testid="streamendref-id" ref={scrollRef} />
      </div>
      <div className="chat-footer">
        <Button
          className="btn-create-conv"
          shape="circular"
          appearance="primary"
          icon={<ChatAdd24Regular />}
          onClick={onNewConversation}
          title="Create new Conversation"
          disabled={isInputDisabled}
        />
        <div className="text-area-container">
          <Textarea
            className="textarea-field"
            value={userMessage}
            onChange={(e, data) => setUserMessageValue(data.value || "")}
            placeholder="Ask a question..."
            onKeyDown={handleKeyDown}
            ref={questionInputRef}
            rows={2}
            style={{ resize: "none" }}
            appearance="outline"
          />
          <DefaultButton
            iconProps={{ iconName: "Send" }}
            role="button"
            onClick={onClickSend}
            disabled={isSendDisabled}
            className="send-button"
            aria-disabled={isSendDisabled}
            title="Send Question"
          />
        </div>
      </div>
    </div>
  );
};

Chat.displayName = "Chat";

export default Chat;
