/**
 * @deprecated – This file is kept only as a re-export shim for
 * backwards compatibility. All utilities have been moved to
 * domain-specific files under `src/utils/`.
 *
 *   chartUtils.ts   – colors, sentimentIcons, defaultSelectedFilters,
 *                     hideDataSetsLabelConfig, ACCEPT_FILTERS,
 *                     getGridStyles, normalize
 *   messageUtils.ts – generateUUIDv4, segregateItems
 *   apiUtils.ts     – retryRequest, RequestCache, throttle, debounce,
 *                     parseErrorMessage
 *   jsonUtils.ts    – safeParse, safeStringify
 *
 * Import directly from `../utils/<domain>` instead.
 */

export {
  colors,
  sentimentIcons,
  defaultSelectedFilters,
  hideDataSetsLabelConfig,
  ACCEPT_FILTERS,
  getGridStyles,
  normalize,
} from "../utils/chartUtils";

export { generateUUIDv4, segregateItems } from "../utils/messageUtils";

export { parseErrorMessage } from "../utils/apiUtils";
