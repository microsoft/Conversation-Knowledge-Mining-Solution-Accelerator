import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Body1, Button, Subtitle2, Textarea } from "@fluentui/react-components";
import { DefaultButton, Spinner, SpinnerSize } from "@fluentui/react";
import { ChatAdd24Regular } from "@fluentui/react-icons";
import "./Chat.css";
import { getIsChartDisplayDefault } from "../../api/api";
import { useAppDispatch, useAppSelector } from "../../state/hooks";
import { setUserMessage } from "../../state/slices/chatSlice";
import { useAutoScroll } from "../../hooks/useAutoScroll";
import { useChatApi } from "../../hooks/useChatApi";
import ChatMessageItem from "./ChatMessageItem";

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
  const userMessage = useAppSelector((state) => state.chat.userMessage);
  const messages = useAppSelector((state) => state.chat.messages);
  const generatingResponse = useAppSelector(
    (state) => state.chat.generatingResponse
  );
  const isStreamingInProgress = useAppSelector(
    (state) => state.chat.isStreamingInProgress
  );
  const isFetchingConvMessages = useAppSelector(
    (state) => state.chatHistory.isFetchingConvMessages
  );
  const isHistoryUpdateAPIPending = useAppSelector(
    (state) => state.chatHistory.isHistoryUpdateAPIPending
  );

  const questionInputRef = useRef<HTMLTextAreaElement | null>(null);
  const [isChartLoading, setIsChartLoading] = useState(false);
  const [isChartDisplayDefault, setIsChartDisplayDefault] = useState(false);

  useEffect(() => {
    let isMounted = true;

    const loadChartDisplayPreference = async () => {
      try {
        const chartConfigFlag = await getIsChartDisplayDefault();
        if (isMounted) {
          setIsChartDisplayDefault(chartConfigFlag.isChartDisplayDefault);
        }
      } catch {
        if (isMounted) {
          setIsChartDisplayDefault(false);
        }
      }
    };

    void loadChartDisplayPreference();

    return () => {
      isMounted = false;
    };
  }, []);

  const { chatMessageStreamEnd, scrollChatToBottom } = useAutoScroll();
  const { sendMessage, startNewChat } = useChatApi({
    scrollChatToBottom,
    setIsChartLoading,
    isChartDisplayDefault,
  });

  useEffect(() => {
    scrollChatToBottom("auto");
  }, [
    generatingResponse,
    isFetchingConvMessages,
    messages.length,
    scrollChatToBottom,
  ]);

  const isInputDisabled = useMemo(
    () => generatingResponse || isHistoryUpdateAPIPending,
    [generatingResponse, isHistoryUpdateAPIPending]
  );

  const handleSend = useCallback(() => {
    if (userMessage.trim()) {
      void sendMessage(userMessage);
    }

    questionInputRef.current?.focus();
  }, [sendMessage, userMessage]);

  const handleKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const handleUserMessageChange = useCallback(
    (_event: unknown, data: { value?: string }) => {
      dispatch(setUserMessage(data.value || ""));
    },
    [dispatch]
  );

  const handleNewConversation = useCallback(() => {
    startNewChat();
    questionInputRef.current?.focus();
  }, [startNewChat]);

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
            {`${panelShowStates[panels.CHATHISTORY] ? "Hide" : "Show"} Chat History`}
          </Button>
        </span>
      </div>
      <div className="chat-messages">
        {isFetchingConvMessages && (
          <div>
            <Spinner
              size={SpinnerSize.small}
              aria-label="Fetching Chat messages"
            />
          </div>
        )}
        {!isFetchingConvMessages && messages.length === 0 && (
          <div className="initial-msg">
            <h2>✨</h2>
            <Subtitle2>Start Chatting</Subtitle2>
            <Body1 style={{ textAlign: "center" }}>
              You can ask questions around customers calls, call topics and
              call sentiments.
            </Body1>
          </div>
        )}
        {!isFetchingConvMessages &&
          messages.map((message, index) => (
            <div key={message.id || index} className={`chat-message ${message.role}`}>
              <ChatMessageItem
                message={message}
                index={index}
                totalMessages={messages.length}
                generatingResponse={generatingResponse}
              />
            </div>
          ))}
        {((generatingResponse && !isStreamingInProgress) || isChartLoading) && (
          <div className="assistant-message loading-indicator">
            <div className="typing-indicator">
              <span className="generating-text">
                {isChartLoading
                  ? "Generating chart if possible with the provided data"
                  : "Generating answer"}
              </span>
              <span className="dot"></span>
              <span className="dot"></span>
              <span className="dot"></span>
            </div>
          </div>
        )}
        <div data-testid="streamendref-id" ref={chatMessageStreamEnd} />
      </div>
      <div className="chat-footer">
        <Button
          className="btn-create-conv"
          shape="circular"
          appearance="primary"
          icon={<ChatAdd24Regular />}
          onClick={handleNewConversation}
          title="Create new Conversation"
          disabled={isInputDisabled}
        />
        <div className="text-area-container">
          <Textarea
            className="textarea-field"
            value={userMessage}
            onChange={handleUserMessageChange}
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
            onClick={handleSend}
            disabled={isInputDisabled || !userMessage.trim()}
            className="send-button"
            aria-disabled={isInputDisabled || !userMessage.trim()}
            title="Send Question"
          />
        </div>
      </div>
    </div>
  );
};

export default Chat;
