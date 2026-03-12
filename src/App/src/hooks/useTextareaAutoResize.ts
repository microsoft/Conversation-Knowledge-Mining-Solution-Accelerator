import { useEffect } from "react";

/**
 * Auto-resizes a `<textarea>` to fit its content, up to an
 * optional maximum number of rows. Resets to a single-row
 * baseline on each change so shrinking works correctly.
 *
 * @param ref   React ref attached to the textarea element
 * @param value The current textarea value (triggers recalc on change)
 * @param maxRows Maximum visible rows before scrolling kicks in (default 6)
 */
export function useTextareaAutoResize(
  ref: React.RefObject<HTMLTextAreaElement>,
  value: string,
  maxRows: number = 6
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Reset to single row so scrollHeight reflects actual content
    el.style.height = "auto";

    const style = window.getComputedStyle(el);
    const lineHeight = parseFloat(style.lineHeight) || 20;
    const paddingTop = parseFloat(style.paddingTop) || 0;
    const paddingBottom = parseFloat(style.paddingBottom) || 0;
    const borderTop = parseFloat(style.borderTopWidth) || 0;
    const borderBottom = parseFloat(style.borderBottomWidth) || 0;

    const maxHeight =
      lineHeight * maxRows + paddingTop + paddingBottom + borderTop + borderBottom;
    const nextHeight = Math.min(el.scrollHeight, maxHeight);

    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > maxHeight ? "auto" : "hidden";
  }, [ref, value, maxRows]);
}
