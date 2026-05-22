import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import supersub from "remark-supersub";
import { type ChatMessage } from "../../types/AppTypes";
import ChatChart from "../ChatChart/ChatChart";
import Citations from "../Citations/Citations";
import { hasChartContent } from "../../utils/chartUtils";
import { parseCitationFromMessage } from "../../utils/messageUtils";

type ChatMessageItemProps = {
  message: ChatMessage;
  index: number;
  totalMessages: number;
  generatingResponse: boolean;
};

const ChatMessageItemComponent: React.FC<ChatMessageItemProps> = ({
  message,
  index,
  totalMessages,
  generatingResponse,
}) => {
  const isLastAssistantMessage =
    message.role === "assistant" && index === totalMessages - 1;

  const parsedAnswer = useMemo(
    () => ({
      answer: typeof message.content === "string" ? message.content : "",
      citations:
        message.role === "assistant"
          ? parseCitationFromMessage(message.citations)
          : [],
    }),
    [message.citations, message.content, message.role]
  );

  if (message.role === "user" && typeof message.content === "string") {
    if (message.content === "show in a graph by default") {
      return null;
    }

    return (
      <div className="user-message">
        <span>{message.content}</span>
      </div>
    );
  }

  if (hasChartContent(message.content)) {
    return (
      <div className="assistant-message chart-message">
        <ChatChart chartContent={message.content} />
        <div className="answerDisclaimerContainer">
          <span className="answerDisclaimer">
            AI-generated content may be incorrect
          </span>
        </div>
      </div>
    );
  }

  if (typeof message.content === "string") {
    return (
      <div
        className={`assistant-message ${
          message.role === "error" ? "error-message" : ""
        }`}
      >
        <ReactMarkdown remarkPlugins={[remarkGfm, supersub]}>
          {message.content}
        </ReactMarkdown>
        {isLastAssistantMessage && generatingResponse ? (
          <div className="typing-indicator">
            <span className="dot"></span>
            <span className="dot"></span>
            <span className="dot"></span>
          </div>
        ) : message.role === "assistant" ? (
          <Citations answer={parsedAnswer} index={index} />
        ) : null}

        <div className="answerDisclaimerContainer">
          <span className="answerDisclaimer">
            AI-generated content may be incorrect
          </span>
        </div>
      </div>
    );
  }

  return null;
};

const ChatMessageItem = React.memo(ChatMessageItemComponent);
ChatMessageItem.displayName = "ChatMessageItem";

export default ChatMessageItem;
