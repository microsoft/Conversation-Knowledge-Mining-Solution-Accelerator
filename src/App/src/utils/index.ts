/**
 * Barrel re-exports for `src/utils/`.
 *
 * Consumers can either import from the barrel:
 *   import { safeParse, generateUUIDv4, colors } from "../utils";
 *
 * Or directly from the domain file:
 *   import { safeParse } from "../utils/jsonUtils";
 */

export { safeParse, safeStringify } from "./jsonUtils";
export { generateUUIDv4, segregateItems } from "./messageUtils";
export type { SegregatedGroup } from "./messageUtils";
export {
  colors,
  sentimentIcons,
  defaultSelectedFilters,
  hideDataSetsLabelConfig,
  ACCEPT_FILTERS,
  getGridStyles,
  normalize,
} from "./chartUtils";
export {
  retryRequest,
  RequestCache,
  throttle,
  debounce,
  parseErrorMessage,
  createErrorResponse,
} from "./apiUtils";
export type { RetryOptions } from "./apiUtils";
export {
  extractAnswerAndCitations,
  parseChartContent,
} from "./chatParsingUtils";
export type {
  AnswerAndCitations,
  ChartParseResult,
} from "./chatParsingUtils";
