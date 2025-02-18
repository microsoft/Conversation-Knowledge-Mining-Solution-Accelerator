const conversations = [
  {
    _attachments: "attachments/",
    _etag: '"1700d350-0000-0400-0000-673aeadc0000"',
    _rid: "L4pzAPJpN2I3AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I3AAAAAAAAAA==/",
    _ts: 1731914460,
    conversationId: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    createdAt: "2024-11-18T07:20:34.325091",
    id: "c6430b2c-3bc6-4259-a695-db31af20e52c",
    title: "Introducing the conversation",
    type: "conversation",
    updatedAt: "2024-11-18T07:21:00.469430",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
  {
    _attachments: "attachments/",
    _etag: '"17003950-0000-0400-0000-673aeacf0000"',
    _rid: "L4pzAPJpN2I7AAAAAAAAAA==",
    _self: "dbs/L4pzAA==/colls/L4pzAPJpN2I=/docs/L4pzAPJpN2I7AAAAAAAAAA==/",
    _ts: 1731914447,
    conversationId: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    createdAt: "2024-11-18T07:20:47.577407",
    id: "128cbe0a-cc7e-4cd6-a217-cfe2547cf1e7",
    title: "Greeting exchange initiation",
    type: "conversation",
    updatedAt: "2024-11-18T07:20:47.707249",
    userId: "4b16c510-aecd-4016-9581-5467bfe2b8f3",
  },
];

export const historyListResponse = [].concat(...Array(0).fill(conversations));
export const historyReadResponse = {
  "conversation_id": "c6430b2c-3bc6-4259-a695-db31af20e52c",
  "messages": [
      {
          "content": "hi",
          "createdAt": "2024-11-27T08:00:38.706Z",
          "feedback": null,
          "id": "301cc2d1-aba6-47a9-8362-f44c63d52ce3",
          "role": "user",
          "context":'',
          "contentType":''
      },
      {
          "content": "Hello! How can I assist you today?",
          "createdAt": "2024-11-27T08:00:38.867Z",
          "feedback": null,
          "id": "a2521228-0f88-401f-9d39-d78e0a3ef2cd",
          "role": "assistant",
           "context":'',
          "contentType":''
      }
  ]
};
export const ChartsResponse = [
  {
    id: "AVG_HANDLING_TIME",
    chart_name: "Average Handling Time",
    chart_type: "card",
    chart_value: [
      {
        name: "Average Handling Time",
        value: 17,
        unit_of_measurement: "mins",
      },
    ],
  },
  {
    id: "Satisfied",
    chart_name: "Satisfied",
    chart_type: "card",
    chart_value: [
      {
        name: "Satisfied",
        value: 100,
        unit_of_measurement: "%",
      },
    ],
  },
  {
    id: "TOTAL_CALLS",
    chart_name: "Total Calls",
    chart_type: "card",
    chart_value: [
      {
        name1: "Total Calls",
        value: 105,
        unit_of_measurement: "",
      },
    ],
  },
  {
    id: "TOPICS",
    chart_name: "Trending Topics",
    chart_type: "table",
    chart_value: [
      {
        name: "Account Information Updates",
        call_frequency: 13,
        average_sentiment: "neutral",
      },
      {
        name: "Appointment Scheduling",
        call_frequency: 8,
        average_sentiment: "neutral",
      },
      {
        name: "Billing and Payment Issues",
        call_frequency: 12,
        average_sentiment: "neutral",
      },
      {
        name: "Customer Feedback",
        call_frequency: 6,
        average_sentiment: "positive",
      },
      {
        name: "Device Troubleshooting",
        call_frequency: 23,
        average_sentiment: "neutral",
      },
      {
        name: "Parental Controls",
        call_frequency: 7,
        average_sentiment: "neutral",
      },
      {
        name: "Promotions and Customer Feedback",
        call_frequency: 13,
        average_sentiment: "neutral",
      },
      {
        name: "Service Activation",
        call_frequency: 23,
        average_sentiment: "neutral",
      },
    ],
  },
  {
    id: "KEY_PHRASES",
    chart_name: "Key Phrases",
    chart_type: "wordcloud",
    chart_value: [
      {
        text: "account number",
        size: 7,
        average_sentiment: "negative",
      },
      {
        text: "customer service",
        size: 16,
        average_sentiment: "neutral",
      },
      {
        text: "network coverage",
        size: 22,
        average_sentiment: "neutral",
      },
      {
        text: "call forwarding",
        size: 20,
        average_sentiment: "negative",
      },
      {
        text: "promotional offers",
        size: 10,
        average_sentiment: "neutral",
      },
      {
        text: "international roaming",
        size: 11,
        average_sentiment: "neutral",
      },
      {
        text: "feedback",
        size: 16,
        average_sentiment: "neutral",
      },
      {
        text: "technical team",
        size: 10,
        average_sentiment: "neutral",
      },
      {
        text: "troubleshooting steps",
        size: 7,
        average_sentiment: "neutral",
      },
    ],
  },
  {
    id: "SENTIMENT",
    chart_name: "Topics Overview",
    chart_type: "donutchart",
    chart_value: [
      {
        name: "positive",
        value: 60,
      },
      {
        name: "neutral",
        value: 10,
      },
      {
        name: "negative",
        value: 30,
      },
    ],
  },
  {
    id: "AVG_HANDLING_TIME_BY_TOPIC",
    chart_name: "Average Handling Time By Topic",
    chart_type: "bar",
    chart_value: [
      {
        name: "Internet Services",
        value: 1,
      },
      {
        name: "Billing and Payment",
        value: 2.8,
      },
      {
        name: "Loyalty Programs",
        value: 3.7,
      },
      {
        name: "International Roaming",
        value: 4,
      },
    ],
  },
];

export const sampleFiltersData = [
  {
    filter_name: "Topic",
    filter_values: [
      { key: "internet-services", displayValue: "Internet Services" },
      {
        key: "billing-and-payment",
        displayValue: "Billing and Payment",
      },
      { key: "loyalty-programs", displayValue: "Loyalty Programs" },
      {
        key: "international-roaming",
        displayValue: "International Roaming",
      },
      { key: "plan-management", displayValue: "Plan Management" },
      { key: "device-support", displayValue: "Device Support" },
      {
        key: "network-connectivity",
        displayValue: "Network Connectivity",
      },
      { key: "parental-controls", displayValue: "Parental Controls" },
    ],
  },
  {
    filter_name: "Sentiment",
    filter_values: [
      { key: "satisfied", displayValue: "Satisfied" },
      { key: "dissatisfied", displayValue: "Dissatisfied" },
      { key: "neutral", displayValue: "Neutral" },
      { key: "all", displayValue: "All" },
    ],
  },
  {
    filter_name: "DateRange",
    filter_values: [
      { key: "7days", displayValue: "Last 7 days" },
      { key: "14days", displayValue: "Last 14 days" },
      { key: "90days", displayValue: "Last 90 days" },
      { key: "yearToDate", displayValue: "Year to Date" },
    ],
  },
];
