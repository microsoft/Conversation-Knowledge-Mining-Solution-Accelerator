import * as React from "react";
import { useEffect, useRef } from "react";
import {
  List,
  Separator,
  Spinner,
  SpinnerSize,
  Stack,
  StackItem,
  Text,
} from "@fluentui/react";
import styles from "./ChatHistoryListItemGroups.module.css";
import { ChatHistoryListItemCell } from "../ChatHistoryListItemCell/ChatHistoryListItemCell";
import { Conversation } from "../../types/AppTypes";
import { useAppContext } from "../../state/useAppContext";
import { segregateItems } from "../../configs/Utils";

export interface GroupedChatHistory {
  title: string;
  entries: Conversation[];
}
interface ChatHistoryListItemGroupsProps {
  handleFetchHistory: () => Promise<void>;
  onSelectConversation: (id: string) => void;
}

export const ChatHistoryListItemGroups: React.FC<
  ChatHistoryListItemGroupsProps
> = ({
  handleFetchHistory,
  onSelectConversation,
}) => {
  const observerTarget = useRef(null);
  const initialCall = useRef(true);
  const { state } = useAppContext();
  const { chatHistory } = state;

  const groupedChatHistory = segregateItems(chatHistory.list);

  const handleSelectHistory = (item?: Conversation) => {
    if (typeof item === "object") {
      onSelectConversation(item?.id);
    }
  };

  const onRenderCell = (item?: Conversation) => {
    return (
      <ChatHistoryListItemCell
        item={item}
        onSelect={() => handleSelectHistory(item)}
        key={item?.id}
      />
    );
  };
  useEffect(() => {
    if (initialCall.current) {
      initialCall.current = false;
    }
  }, []);

  useEffect(() => {
    if (initialCall.current) {
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          if (!chatHistory?.fetchingConversations) {
            handleFetchHistory();
          }
        }
      },
      { threshold: 1 }
    );

    if (observerTarget.current) observer.observe(observerTarget.current);

    return () => {
      if (observerTarget.current) observer.unobserve(observerTarget.current);
    };
  }, [observerTarget.current, chatHistory?.fetchingConversations]);

  const allConversationsLength = groupedChatHistory.reduce(
    (previousValue, currentValue) =>
      previousValue + currentValue.entries.length,
    0
  );

  if (!chatHistory.fetchingConversations && allConversationsLength === 0) {
    return (
      <Stack
        horizontal
        horizontalAlign="center"
        verticalAlign="center"
        style={{ width: "100%", marginTop: 10 }}
      >
        <StackItem>
          <Text
            style={{ alignSelf: "center", fontWeight: "400", fontSize: 14 }}
          >
            <span>No chat history.</span>
          </Text>
        </StackItem>
      </Stack>
    );
  }

  return (
    <div
      id="historyListContainer"
      className={styles.listContainer}
      data-is-scrollable
    >
      {groupedChatHistory.map(
        (group, index) =>
          group.entries.length > 0 && (
            <Stack
              horizontalAlign="start"
              verticalAlign="center"
              key={`GROUP-${group.title}-${index}`}
              className={styles.chatGroup}
              aria-label={`chat history group: ${group.title}`}
            >
              <Stack aria-label={group.title} className={styles.chatMonth}>
                {group.title}
              </Stack>
              <List
                aria-label={`chat history list`}
                items={group.entries}
                onRenderCell={onRenderCell}
                className={styles.chatList}
              />
            </Stack>
          )
      )}
      <div id="chatHistoryListItemObserver" ref={observerTarget} />
      <Separator
        styles={{
          root: {
            width: "100%",
            padding: "0px",
            height: "2px",
            position: "relative",
            "::before": {
              backgroundColor: "#d6d6d6",
            },
          },
        }}
      />
      {Boolean(chatHistory?.fetchingConversations) && (
        <div className={styles.spinnerContainer}>
          <Spinner
            size={SpinnerSize.small}
            aria-label="loading more chat history"
            className={styles.spinner}
          />
        </div>
      )}
    </div>
  );
};
