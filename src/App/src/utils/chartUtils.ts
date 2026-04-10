/**
 * Chart-display configuration, layout math, and visual helpers.
 *
 * Extracted from the monolithic `configs/Utils.tsx`.
 * Internal helpers (`getEqualWidgetsWidth`, `getCustomWidgetsWidth`,
 * `getNormalizedHeight`, `widgetsContainerMaxHeight`, `ACCEPT_FILTERS`)
 * are intentionally **not** exported — they are consumed only within this
 * module and keeping them private reduces the public API surface.
 */

// ──────────────────────────────────────────────
//  Colour / icon palettes
// ──────────────────────────────────────────────

export const colors: Record<string, string> = {
  positive: "#6576F9",
  neutral: "#B2BBFC",
  negative: "#FF749B",
  default: "#ccc",
};

export const sentimentIcons: Record<string, string> = {
  satisfied: "Emoji2",
  neutral: "EmojiNeutral",
  dissatisfied: "Sad",
};

// ──────────────────────────────────────────────
//  Default filter preset
// ──────────────────────────────────────────────

export const defaultSelectedFilters = {
  Topic: [] as string[],
  Sentiment: ["all"],
  DateRange: ["Year to Date"],
};

// ──────────────────────────────────────────────
//  Chart.js legend config
// ──────────────────────────────────────────────

export const hideDataSetsLabelConfig = {
  display: true,
  labels: {
    filter: function () {
      // Hide all dataset labels from the legend
      return false;
    },
  },
};

// ──────────────────────────────────────────────
//  Internal layout constants & helpers
// ──────────────────────────────────────────────

/** @internal Maximum height for the widgets container (vh). */
const widgetsContainerMaxHeight = 81;

/** Accepted filter keys. */
export const ACCEPT_FILTERS = ["Topic", "Sentiment", "DateRange"];

/** @internal Equal-width distribution for n widgets. */
function getEqualWidgetsWidth(
  noOfWidgets: number,
  gapInPercentage: number
): number {
  return (100 - (noOfWidgets - 1) * gapInPercentage) / noOfWidgets;
}

/** @internal Custom-width distribution when a widget declares its own width. */
function getCustomWidgetsWidth(
  noOfWidgets: number,
  gapInPercentage: number,
  spaceToOccupyInPercentage: number = 50
): number {
  const availableWidth = 100 - (noOfWidgets - 1) * gapInPercentage;
  return (spaceToOccupyInPercentage * availableWidth) / 100;
}

/** @internal Normalise a height value against the max container height. */
function getNormalizedHeight(height: number): number {
  return (height * widgetsContainerMaxHeight) / 100;
}

// ──────────────────────────────────────────────
//  Public layout API
// ──────────────────────────────────────────────

/**
 * Compute CSS-Grid `gridTemplateColumns` / `gridTemplateRows` from a
 * list of chart config objects.
 */
export const getGridStyles = (
  chartsList: any,
  widgetsGapInPercentage: number
): { gridTemplateColumns: string; gridTemplateRows: string } => {
  const styles = {
    gridTemplateColumns: "auto",
    gridTemplateRows: "auto",
  };

  try {
    if (!Array.isArray(chartsList)) return styles;

    const isWidthExists = chartsList.some(
      (chartObj) => chartObj?.layout?.width
    );

    if (!isWidthExists) {
      const widgetWidth = getEqualWidgetsWidth(
        chartsList.length,
        widgetsGapInPercentage
      );
      styles.gridTemplateColumns = String(widgetWidth + "% ")
        .repeat(chartsList.length)
        .trim();
    } else {
      chartsList.sort((a: any, b: any) => a?.layout?.column - b?.layout?.column);
      const value = chartsList.reduce(
        (acc: string, current: any) =>
          acc +
          " " +
          getCustomWidgetsWidth(
            chartsList.length,
            widgetsGapInPercentage,
            current?.layout?.width
          ) +
          "% ",
        ""
      );
      styles.gridTemplateColumns = value.trim();
    }

    const heightValObj = chartsList.find(
      (chartObj: any) => chartObj?.layout?.height
    );
    if (heightValObj) {
      styles.gridTemplateRows =
        getNormalizedHeight(heightValObj?.layout?.height) + "vh";
    }

    return styles;
  } catch {
    return styles;
  }
};

// ──────────────────────────────────────────────
//  Numeric normalization for word-cloud sizing
// ──────────────────────────────────────────────

/**
 * Linearly map `x` from `originalRange` into `referenceRange`.
 * When the original range is degenerate (min === max) the reference
 * range is used directly.
 */
export function normalize(
  x: number,
  originalRange: number[],
  referenceRange: number[]
): number {
  let [x1, x2] = originalRange;
  const [y1, y2] = referenceRange;

  if (x1 === x2) {
    x1 = y1;
    x2 = y2;
  }

  const y = y1 + ((x - x1) * (y2 - y1)) / (x2 - x1);
  return y >= y1 ? y : y1;
}
