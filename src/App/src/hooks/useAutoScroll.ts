import { useCallback, useRef } from "react";

export const useAutoScroll = () => {
  const chatMessageStreamEnd = useRef<HTMLDivElement | null>(null);

  const scrollChatToBottom = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      if (!chatMessageStreamEnd.current) {
        return;
      }

      setTimeout(() => {
        chatMessageStreamEnd.current?.scrollIntoView({ behavior });
      }, 100);
    },
    []
  );

  return {
    chatMessageStreamEnd,
    scrollChatToBottom,
  };
};
