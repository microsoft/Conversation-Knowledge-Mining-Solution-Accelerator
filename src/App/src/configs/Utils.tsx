import { Conversation } from "../types/AppTypes";

export const colors: { [key: string]: string } = {
  positive: "#6576F9",
  neutral: "#B2BBFC",
  negative: "#FF749B",
  default: "#ccc", // Fallback color for any undefined sentiment
};

export const sentimentIcons: { [key: string]: string } = {
  satisfied: "Emoji2",
  neutral: "EmojiNeutral",
  dissatisfied: "Sad",
};

export const defaultSelectedFilters = {
  Topic: [],
  Sentiment: ["all"],
  DateRange: ["Year to Date"],
};

export const widgetsContainerMaxHeight = 81; // in vh
export const ACCEPT_FILTERS = ["Topic", "Sentiment", "DateRange"];
export const getEqualWidgetsWidth = (
  noOfWidgets: number,
  gapInPercentage: number
): number => {
  return (100 - (noOfWidgets - 1) * gapInPercentage) / noOfWidgets;
};

export const getCustomWidgetsWidth = (
  noOfWidgets: number,
  gapInPercentage: number,
  spaceToOccupyInPercentage: number = 50
): number => {
  const availableWidth = 100 - (noOfWidgets - 1) * gapInPercentage;
  return (spaceToOccupyInPercentage * availableWidth) / 100;
};

export const getNormalizedHeight = (height: number) => {
  return (height * widgetsContainerMaxHeight) / 100;
};

export const getGridStyles = (
  chartsList: any,
  widgetsGapInPercentage: number
) => {
  const styles: {
    gridTemplateColumns: string;
    gridTemplateRows: string;
  } = { gridTemplateColumns: "auto", gridTemplateRows: "auto" };
  try {
    if (Array.isArray(chartsList)) {
      const isWidthExists = chartsList.some(
        (chartObj) => chartObj?.layout?.width
      );
      // Equal distribution of available space calculate
      if (!isWidthExists) {
        const widgetWidth = getEqualWidgetsWidth(
          chartsList.length,
          widgetsGapInPercentage
        );
        styles.gridTemplateColumns = String(widgetWidth + "% ")
          .repeat(chartsList.length)
          .trim();
      }
      if (isWidthExists) {
        chartsList.sort((a, b) => a?.layout?.column - b?.layout?.column);
        const value = chartsList.reduce(
          (acc, current) =>
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
        (chartObj) => chartObj?.layout?.height
      );
      if (heightValObj) {
        styles.gridTemplateRows =
          getNormalizedHeight(heightValObj?.layout?.height) + "vh";
      }
      return styles;
    }
    return styles;
  } catch (e) {
    return styles;
  }
};

export function isLastSevenDaysRange(dateToCheck: any) {
  // Get the current date
  const currentDate = new Date();
  // Calculate the date 2 days ago
  const twoDaysAgo = new Date();
  twoDaysAgo.setDate(currentDate.getDate() - 2);
  // Calculate the date 8 days ago
  const eightDaysAgo = new Date();
  eightDaysAgo.setDate(currentDate.getDate() - 8);
  // Ensure the comparison dates are in the correct order
  // We need eightDaysAgo to be earlier than twoDaysAgo
  return dateToCheck >= eightDaysAgo && dateToCheck <= twoDaysAgo;
}

export const segregateItems = (items: Conversation[]) => {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  // Sort items by updatedAt in descending order
  items.sort(
    (a, b) =>
      new Date(b.updatedAt ? b.updatedAt : new Date()).getTime() -
      new Date(a.updatedAt ? a.updatedAt : new Date()).getTime()
  );
  const groupedItems: {
    Today: Conversation[];
    Yesterday: Conversation[];
    Last7Days: Conversation[];
    Older: Conversation[];
    Past: { [key: string]: Conversation[] };
  } = {
    Today: [],
    Yesterday: [],
    Last7Days: [],
    Older: [],
    Past: {},
  };

  items.forEach((item) => {
    const itemDate = new Date(item.updatedAt ? item.updatedAt : new Date());
    const itemDateOnly = itemDate.toDateString();
    if (itemDateOnly === today.toDateString()) {
      groupedItems.Today.push(item);
    } else if (itemDateOnly === yesterday.toDateString()) {
      groupedItems.Yesterday.push(item);
    } else if (isLastSevenDaysRange(itemDate)) {
      groupedItems.Last7Days.push(item);
    } else {
      groupedItems.Older.push(item);
    }
  });

  const finalResult = [
    { title: `Today`, entries: groupedItems.Today },
    {
      title: `Yesterday`,
      entries: groupedItems.Yesterday,
    },
    {
      title: `Last 7 days`,
      entries: groupedItems.Last7Days,
    },
    {
      title: `Older`,
      entries: groupedItems.Older,
    },
  ];

  return finalResult;
};

export async function loadConfig() {
  const DEFAULT_CONFIG_PATH = "./config/config.json";
  const configPath = process.env.REACT_APP_CONFIG_PATH || DEFAULT_CONFIG_PATH;
  if (!configPath) {
    throw new Error("Config path is not defined in the environment variables.");
  }

  try {
    const response = await fetch(configPath);
    if (!response.ok) {
      throw new Error(`Failed to load config file: ${response.statusText}`);
    }
    const configData = await response.json();
    return configData;
  } catch (error) {
    console.error("Error loading config:", error);
    throw error;
  }
}

export const generateUUIDv4 = () => {
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
    var r = (Math.random() * 16) | 0,
      v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};


export function normalize(
  x: number,
  originalRange: number[],
  referenceRange: number[]
) {
  // Destructure the ranges into their min and max values

  let [x1, x2] = originalRange;
  const [y1, y2] = referenceRange;
  //orginalrange min and max values are same 
  if (x1 === x2) {
    x1 = y1;
    x2 = y2;
  }

  // Apply the normalization formula
  const y = y1 + ((x - x1) * (y2 - y1)) / (x2 - x1);
  return y >= y1 ? y : y1;
}


export const tryGetRaiPrettyError = (errorMessage: string) => {
  try {
    // Using a regex to extract the JSON part that contains "innererror"
    const match = errorMessage.match(/'innererror': ({.*})\}\}/)
    if (match) {
      // Replacing single quotes with double quotes and converting Python-like booleans to JSON booleans
      const fixedJson = match[1]
        .replace(/'/g, '"')
        .replace(/\bTrue\b/g, 'true')
        .replace(/\bFalse\b/g, 'false')
      const innerErrorJson = JSON.parse(fixedJson)
      let reason = ''
      // Check if jailbreak content filter is the reason of the error
      const jailbreak = innerErrorJson.content_filter_result.jailbreak
      if (jailbreak.filtered === true) {
        reason = 'Jailbreak'
      }

      // Returning the prettified error message
      if (reason !== '') {
        return (
          'The prompt was filtered due to triggering Azure OpenAI’s content filtering system.\n' +
          'Reason: This prompt contains content flagged as ' +
          reason +
          '\n\n' +
          'Please modify your prompt and retry. Learn more: https://go.microsoft.com/fwlink/?linkid=2198766'
        )
      }
    }
  } catch (e) {
    console.error('Failed to parse the error:', e)
  }
  return errorMessage
}

export const parseErrorMessage = (errorMessage: string) => {
  let errorCodeMessage = errorMessage.substring(0, errorMessage.indexOf('-') + 1)
  const innerErrorCue = "{\\'error\\': {\\'message\\': "
  if (errorMessage.includes(innerErrorCue)) {
    try {
      let innerErrorString = errorMessage.substring(errorMessage.indexOf(innerErrorCue))
      if (innerErrorString.endsWith("'}}")) {
        innerErrorString = innerErrorString.substring(0, innerErrorString.length - 3)
      }
      innerErrorString = innerErrorString.replaceAll("\\'", "'")
      let newErrorMessage = errorCodeMessage + ' ' + innerErrorString
      errorMessage = newErrorMessage
    } catch (e) {
      console.error('Error parsing inner error message: ', e)
    }
  }

  return tryGetRaiPrettyError(errorMessage)
}

export const hideDataSetsLabelConfig = {
  display: true,
  labels: {
    filter: function () {
      // This will hide all dataset labels from the legend
      return false;
    },
  },
}