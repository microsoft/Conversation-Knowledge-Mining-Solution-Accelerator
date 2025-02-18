import React from "react";
import "./ChatHistory.css";

const ChatHistory: React.FC = () => {
  return (
    <div className="chat-history-container">
      <div className="chat-history-header">Chat History</div>
      <div className="chat-history-list">
        <div className="initial-msg">
          {/* <span>Chat History</span> */}
          <span>Coming soon...</span>
        </div>
      </div>
    </div>
  );
};

export default ChatHistory;
