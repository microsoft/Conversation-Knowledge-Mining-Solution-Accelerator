/**
 * Message- and conversation-history utilities.
 *
 * Extracted from the monolithic `configs/Utils.tsx`.
 * `isLastSevenDaysRange` is intentionally **not** exported – it
 * is an internal helper consumed only by `segregateItems`.
 */

import { Conversation } from "../types/AppTypes";

// ──────────────────────────────────────────────
//  UUID generation
// ──────────────────────────────────────────────

export const generateUUIDv4 = (): string => {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

// ──────────────────────────────────────────────
//  Date helpers (internal)
// ──────────────────────────────────────────────

/**
 * Returns `true` when `dateToCheck` falls in the range (8 days ago, 2 days ago].
 * @internal – only used by `segregateItems`.
 */
function isLastSevenDaysRange(dateToCheck: Date): boolean {
  const currentDate = new Date();

  const twoDaysAgo = new Date();
  twoDaysAgo.setDate(currentDate.getDate() - 2);

  const eightDaysAgo = new Date();
  eightDaysAgo.setDate(currentDate.getDate() - 8);

  return dateToCheck >= eightDaysAgo && dateToCheck <= twoDaysAgo;
}

// ──────────────────────────────────────────────
//  Conversation-history grouping
// ──────────────────────────────────────────────

export interface SegregatedGroup {
  title: string;
  entries: Conversation[];
}

/**
 * Sort conversations by `updatedAt` descending and bucket them
 * into Today / Yesterday / Last 7 Days / Older.
 */
export const segregateItems = (items: Conversation[]): SegregatedGroup[] => {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  // Sort descending by updatedAt
  items.sort(
    (a, b) =>
      new Date(b.updatedAt ?? new Date()).getTime() -
      new Date(a.updatedAt ?? new Date()).getTime()
  );

  const grouped = {
    Today: [] as Conversation[],
    Yesterday: [] as Conversation[],
    Last7Days: [] as Conversation[],
    Older: [] as Conversation[],
  };

  items.forEach((item) => {
    const itemDate = new Date(item.updatedAt ?? new Date());
    const itemDateOnly = itemDate.toDateString();

    if (itemDateOnly === today.toDateString()) {
      grouped.Today.push(item);
    } else if (itemDateOnly === yesterday.toDateString()) {
      grouped.Yesterday.push(item);
    } else if (isLastSevenDaysRange(itemDate)) {
      grouped.Last7Days.push(item);
    } else {
      grouped.Older.push(item);
    }
  });

  return [
    { title: "Today", entries: grouped.Today },
    { title: "Yesterday", entries: grouped.Yesterday },
    { title: "Last 7 days", entries: grouped.Last7Days },
    { title: "Older", entries: grouped.Older },
  ];
};
