# Knowledge Mining Platform – BYOD (Azure AI Search) Test Plan

## Application Overview

The Knowledge Mining Platform is a web app that turns an Azure AI Search index into a conversational, chart-driven knowledge base. The target deployment (https://app-ckmrf311nvy4n.azurewebsites.net/) is running in **BYOD – Azure AI Search** mode with 188 indexed records sourced from an IT helpdesk dataset (topics like Hardware setup, Performance troubleshooting, Identity and access management, etc.). The app exposes three top-level tabs: **Home** (connection overview + capability tiles), **Insights** (AI-generated dashboard with Data overview, Suggested explorations, AI findings, Unexpected patterns, Knowledge distribution, KPI snapshot, Tip), and **Explore** (chat surface with filter dimensions for Entities, Topics, Key Phrases; Sources panel; History panel; New conversation; Send). This plan covers happy paths, navigation, dashboard rendering, filter-scoped querying, chat history behavior, and edge/error cases such as empty input, filter clearing, and repeated question submission. Assumes the app starts in a fresh state (no active chat history retained per test).

## Test Scenarios

### 1. home

**Seed:** `tests/seed.spec.ts`

#### 1.1. home page renders header, navigation, and capability tiles

**File:** `tests/home/home-landing.spec.ts`

**Steps:**
  1. Navigate to the app root URL
    - expect: Page title is 'Knowledge Mining Platform'
    - expect: Header shows the 'Knowledge Mining' brand and a 'Sign in' button
    - expect: Navigation exposes Home, Insights, and Explore tabs
    - expect: Hero card shows 'Turn your data into answers and insights' with the 'Upload supported files to enrich your knowledge base.' subtitle
    - expect: 'Azure AI Search Connection' panel is visible with 'View insights' and 'Explore data' actions
    - expect: 'What you can do' section lists three tiles: 'Extract insights', 'Ask questions', and 'Structure outputs'

#### 1.2. View insights CTA on Home routes to the Insights dashboard

**File:** `tests/home/view-insights-cta.spec.ts`

**Steps:**
  1. Navigate to the app root URL
    - expect: Home tab is active
  2. Click the 'View insights' button in the Azure AI Search Connection panel
    - expect: URL becomes /insights
    - expect: Insights tab becomes active
    - expect: The dashboard groups (Data overview, Suggested explorations, AI findings) eventually render

#### 1.3. Explore data CTA on Home routes to the Explore chat surface

**File:** `tests/home/explore-data-cta.spec.ts`

**Steps:**
  1. Navigate to the app root URL
    - expect: Home tab is active
  2. Click the 'Explore data' button in the Azure AI Search Connection panel
    - expect: URL becomes /explore
    - expect: Records counter, source chip 'source: azure_search', and Ask a question textbox are visible

### 2. navigation

**Seed:** `tests/seed.spec.tsz`

#### 2.1. top navigation switches between Home, Insights, and Explore

**File:** `tests/navigation/tab-switching.spec.ts`

**Steps:**
  1. Navigate to the app root URL
    - expect: Home tab is active and URL path is '/'
  2. Click the Insights tab
    - expect: URL path becomes '/insights'
    - expect: Insights tab is active
  3. Click the Explore tab
    - expect: URL path becomes '/explore'
    - expect: Explore tab is active
    - expect: Chat textbox 'Ask a question...' is visible
  4. Click the Home tab
    - expect: URL path becomes '/'
    - expect: Home tab is active
    - expect: 'Azure AI Search Connection' panel is visible

#### 2.2. Ask your data header shortcut appears outside the Explore tab

**File:** `tests/navigation/ask-your-data-header-shortcut.spec.ts`

**Steps:**
  1. Navigate to the app root URL and click the Insights tab
    - expect: An 'Ask your data' button appears in the top header next to 'Sign in'
  2. Click the 'Ask your data' header button
    - expect: URL path becomes '/explore'
    - expect: Chat textbox 'Ask a question...' is visible

### 3. insights

**Seed:** `tests/seed.spec.ts`

#### 3.1. Insights dashboard renders all top-level sections

**File:** `tests/insights/dashboard-sections.spec.ts`

**Steps:**
  1. Navigate directly to /insights and wait for the loading indicator to disappear
    - expect: Data overview section is visible with 'A quick snapshot of record count, extracted topics, entities, and links.'
    - expect: AI layout section is visible with the caption 'Dynamic blocks chosen by the model for this dataset.'
    - expect: Suggested explorations section is visible with 'Conversation-ready prompts to drill into AI findings.'
    - expect: AI findings section is visible with the caption 'Ranked by impact score, confidence, and evidence.'
    - expect: Unexpected patterns section is visible with 'Timeline view of notable deviations and AI-detected shifts.'
    - expect: Knowledge distribution section is visible with 'See which topics dominate and which entities are mentioned most.'
    - expect: KPI snapshot section is visible with 'Top-ranked KPI values with trend and confidence context.'
    - expect: Tip block is visible with text starting 'Use the Explore page to dig into a finding'

#### 3.2. Refresh action reloads dashboard content without leaving the Insights page

**File:** `tests/insights/refresh-dashboard.spec.ts`

**Steps:**
  1. Navigate to /insights and wait for the dashboard to finish loading
    - expect: The Data overview and AI layout sections are visible
  2. Click the 'Refresh' button at the top of the dashboard
    - expect: URL remains /insights
    - expect: A loading state is briefly indicated on the top group
    - expect: Dashboard sections re-render without navigating away

#### 3.3. Data overview quick actions expose additional metrics and route to Explore

**File:** `tests/insights/data-overview-actions.spec.ts`

**Steps:**
  1. Navigate to /insights and wait for the dashboard
    - expect: 'Data overview' section shows 'Show additional metrics' and 'Go to Explore' buttons
  2. Click 'Show additional metrics'
    - expect: Additional metric groups are revealed inside the Data overview section (visible group count grows)
  3. Click 'Go to Explore'
    - expect: URL path becomes '/explore'
    - expect: The chat textbox 'Ask a question...' is visible

#### 3.4. Suggested exploration prompt seeds the Explore chat

**File:** `tests/insights/suggested-exploration-prompt.spec.ts`

**Steps:**
  1. Navigate to /insights and wait for the 'Suggested explorations' section
    - expect: At least six suggested prompt buttons are visible, including 'How do the findings change by support topic?' and 'What should we prioritize in the next 7 days based on these findings?'
  2. Click the 'How do the findings change by support topic?' prompt
    - expect: The app navigates to /explore
    - expect: The prompt text appears in the chat as the user's question and an AI response begins to render

#### 3.5. Help tooltips are reachable for dashboard groups

**File:** `tests/insights/help-tooltips.spec.ts`

**Steps:**
  1. Navigate to /insights and wait for the dashboard
    - expect: 'Document findings help' and 'Knowledge distribution help' buttons are visible
  2. Click the 'Document findings help' button
    - expect: A help affordance is shown for the AI findings section (tooltip / popover / expanded content appears)
  3. Click the 'Knowledge distribution help' button
    - expect: A help affordance is shown for the Knowledge distribution section

### 4. explore

**Seed:** `tests/seed.spec.ts`

#### 4.1. Explore surface shows record counter, source chip, and filter dimensions

**File:** `tests/explore/surface-defaults.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: Records counter reads '188 records'
    - expect: A '1 ready source' indicator is visible
    - expect: A removable filter chip 'source: azure_search' is visible next to a 'History (N)' button
    - expect: Filter dimensions area shows 'Entities (11)', 'Topics (20)', and 'Key Phrases (20)' buttons
    - expect: Ask a question textbox is visible and the Send button is disabled while the textbox is empty

#### 4.2. expanding a filter dimension reveals its values

**File:** `tests/explore/filter-dimension-expansion.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: 'Topics (20)' button is visible and not marked active
  2. Click the 'Topics (20)' button
    - expect: 'Topics (20)' becomes active
    - expect: At least one topic value button (for example, 'Hardware setup', 'Performance troubleshooting', or 'Identity and access management') is visible below it
  3. Click the 'Entities (11)' button
    - expect: 'Entities (11)' becomes active and entity value buttons are shown
  4. Click the 'Key Phrases (20)' button
    - expect: 'Key Phrases (20)' becomes active and key phrase value buttons are shown

#### 4.3. Sources panel shows the connected Azure AI Search source with record count

**File:** `tests/explore/sources-panel.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: A 'Sources' button is visible and a chip for 'azure_search' shows '188' records
  2. Click the 'Sources' button
    - expect: 'Sources' becomes active
    - expect: A '1 sources hidden' hint (or equivalent sources-panel content) is shown

#### 4.4. removing the source filter chip clears the source constraint

**File:** `tests/explore/remove-source-chip.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: A 'source: azure_search' chip with a 'Remove filter' (x) control is visible
  2. Click the 'Remove filter' (x) control on the 'source: azure_search' chip
    - expect: The 'source: azure_search' chip is no longer visible
    - expect: The Ask a question textbox remains usable and the Send button state reflects the current textbox content

#### 4.5. Send button becomes enabled only when the question textbox has content

**File:** `tests/explore/send-button-enablement.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: Send button is disabled while the 'Ask a question...' textbox is empty
  2. Type 'Summarize the main topics.' into the textbox
    - expect: Send button becomes enabled
  3. Clear the textbox
    - expect: Send button becomes disabled again

#### 4.6. asking a BYOD sample question returns a grounded answer

**File:** `tests/explore/ask-summarize-topics.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: Ask a question textbox is visible
  2. Type 'Summarize the main topics.' and click Send
    - expect: The user question 'Summarize the main topics.' is echoed in the conversation
    - expect: An AI response referring to the 188 documents is rendered (mentions text such as 'Main topics across the 188 documents')
    - expect: The response contains a list of topics with occurrence counts drawn from the indexed data
    - expect: A disclaimer 'AI-generated content may be incorrect' appears with the response
    - expect: The History button counter increases by 1 compared to before sending

#### 4.7. asking a categorical sample question returns a ranked breakdown

**File:** `tests/explore/ask-top-categories.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: Ask a question textbox is visible
  2. Type 'What are the top categories by volume?' and click Send
    - expect: The user question is echoed in the conversation
    - expect: The AI response contains an ordered or ranked breakdown of categories (for example a bulleted or numbered list with counts / percentages)
    - expect: 'AI-generated content may be incorrect' disclaimer is shown

#### 4.8. New conversation clears the current chat thread

**File:** `tests/explore/new-conversation.spec.ts`

**Steps:**
  1. Navigate to /explore, type 'Summarize the main topics.', and click Send
    - expect: Both the user question and an AI response are visible in the chat
  2. Click the 'New conversation' button
    - expect: The chat area returns to the 'Ask your data' empty state (welcome copy 'Summaries, trends, and analysis — all through conversation.' is visible)
    - expect: The previous prompt/answer pair is no longer visible in the current thread
    - expect: The prior thread is still accessible from History (History counter is at least 1 higher than it was before the send)

#### 4.9. chat History panel lists prior conversations and can be dismissed

**File:** `tests/explore/history-panel.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: 'History (N)' button is visible with N ≥ 1
  2. Click the 'History (N)' button
    - expect: A 'Chat History' panel opens on the right
    - expect: A 'New conversation' entry appears at the top of the history list
    - expect: At least one prior conversation entry is shown with a title and a '<count> messages' label
    - expect: A close (x) control is visible on the Chat History panel
  3. Click the close (x) control on the Chat History panel
    - expect: The Chat History panel closes
    - expect: The chat surface returns to focus

#### 4.10. opening a prior conversation restores its messages

**File:** `tests/explore/reopen-history-conversation.spec.ts`

**Steps:**
  1. Navigate to /explore and click the 'History (N)' button
    - expect: Chat History panel is open with at least one prior conversation entry
  2. Click the first prior conversation entry (for example an entry titled 'Main Topics Summary' with '4 messages')
    - expect: The Chat History panel closes or collapses
    - expect: The chat area now shows the messages from that prior conversation (both the user question(s) and the AI response(s))

#### 4.11. topic filter selection is respected by a follow-up question

**File:** `tests/explore/topic-filter-scoped-question.spec.ts`

**Steps:**
  1. Navigate to /explore and click the 'Topics (20)' button to expand topic values
    - expect: Topic value buttons such as 'Hardware setup' are visible
  2. Click the 'Hardware setup' topic value
    - expect: A filter indicator for topic 'Hardware setup' is visible (topic chip, active state, or updated records count)
  3. Type 'What are the top key phrases in the filtered records?' and click Send
    - expect: An AI response is returned
    - expect: The response references the 'Hardware setup' scope (mentions the topic name or reflects a reduced record set in its wording)

#### 4.12. Send does nothing while the input is blank

**File:** `tests/explore/blank-send-noop.spec.ts`

**Steps:**
  1. Navigate to /explore
    - expect: Ask a question textbox is empty and the Send button is disabled
  2. Focus the textbox and press Enter without typing anything
    - expect: No new message appears in the chat area
    - expect: The empty state welcome copy 'Ask your data' / 'Summaries, trends, and analysis — all through conversation.' remains visible
    - expect: The History counter does not change

#### 4.13. whitespace-only input is not accepted as a question

**File:** `tests/explore/whitespace-only-input.spec.ts`

**Steps:**
  1. Navigate to /explore and type five spaces into the textbox
    - expect: The Send button remains disabled (or, if enabled, clicking it produces no user message)
  2. Click Send (or press Enter)
    - expect: No user message with whitespace-only content is added to the chat
    - expect: History counter does not increase
