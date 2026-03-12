import { useCallback, useEffect, useRef } from "react";

/**
 * Manages a sentinel element ref and auto-scrolls to it whenever
 * any value in `deps` changes. Returns the ref to attach to a
 * sentinel `<div>` at the bottom of a scrollable container and
 * an imperative `scrollToBottom` helper.
 */
export function useAutoScroll(deps: unknown[]) {
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback((behavior: ScrollBehavior = "smooth") => {
    if (scrollRef.current) {
      setTimeout(() => {
        scrollRef.current?.scrollIntoView({ behavior });
      }, 100);
    }
  }, []);

  // Auto-scroll whenever any dependency changes
  useEffect(() => {
    scrollToBottom();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { scrollRef, scrollToBottom } as const;
}
