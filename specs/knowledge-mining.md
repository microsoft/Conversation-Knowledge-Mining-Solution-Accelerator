# Knowledge Mining Platform — Test Plan

## Application Overview

End-to-end functional test plan for the Knowledge Mining Platform web app deployed at
https://app-ckmmpoxx4d.azurewebsites.net/. The app is the front-end for the Microsoft
Conversation-Knowledge-Mining-Solution-Accelerator. It exposes three top-level views:

- **Home** — landing page that shows the loaded scenario pack, an upload dropzone, and
  "Getting started" cards.
- **Insights** — auto-generated AI dashboard (`Unified Knowledge Insights`) with KPIs,
  topic intensity, timeline patterns, AI findings, and knowledge distribution charts.
- **Explore** — dataset browser + natural-language chat ("Ask your data") with a
  sources list, filter dimensions, and chat history.

Repo scenario discovery found the following scenarios in `data/config/scenarios.json`
and sample questions in `docs/SampleQuestions.md`:

- contact-center, mortgage-application, telecom-analysis, azure_search_byod, fabric_byod, skip

The live app at the provided URL is loaded with the **Telecom Analysis Dataset**
(10 processed files, 5 `.wav` + 5 `.json`), detected from the Home page dataset card.
The three Telecom Analysis sample questions from `docs/SampleQuestions.md` are covered
verbatim as dedicated chat scenarios below.

Auth: the top bar shows a `Sign in` button, but all observed surfaces (Home / Insights /
Explore / Chat / History) are reachable anonymously in this deployment. Tests use the
seed file `tests/seed.spec.ts` as the bootstrap fixture — the generator should extend
that seed to open the app URL (and, if required in the future, wire an auth state).

All tests assume a fresh browser context (blank cookies / localStorage) and start by
navigating to the app URL. Data-specific assertions are scoped to the Telecom Analysis
dataset (e.g., 10 records, wav/json source types, telecom-flavored topics such as
"factory reset", "Voicemail and call forwarding setup", "Reporting and securing a lost
phone").

## Test Scenarios

### 1. home

**Seed:** `tests/seed.spec.ts`

#### 1.1. Home page renders scenario summary and primary navigation

**File:** `tests/knowledge-mining/home-landing.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/
    - expect: The page title is 'Knowledge Mining Platform'.
    - expect: The top bar shows the 'Knowledge Mining' brand and a 'Sign in' button.
    - expect: A navigation bar shows exactly three items: 'Home', 'Insights', 'Explore', with 'Home' selected.
  2. Observe the hero section on the Home view.
    - expect: A heading reading 'Turn your data into answers and insights' is visible.
    - expect: A subtitle reading 'Upload supported files to enrich your knowledge base.' is visible.
  3. Observe the loaded-dataset summary card in the hero row.
    - expect: A card labeled 'Telecom Analysis Dataset' is visible.
    - expect: The card shows '✓ 10 processed' and '📎 10 files'.
  4. Observe the 'Getting started' section under the hero.
    - expect: A section heading 'Getting started' is visible.
    - expect: Three getting-started cards are visible: 'Upload files', 'Connect external data', 'Load a scenario pack'.
    - expect: The 'Load a scenario pack' card mentions the './infra/scripts/post-provision/setup-data.ps1' command.

#### 1.2. Upload dropzone advertises all supported file formats

**File:** `tests/knowledge-mining/home-upload-dropzone.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/ and locate the upload dropzone in the hero section.
    - expect: The dropzone shows the label 'Upload supported files'.
    - expect: The dropzone shows the helper text 'Drag & drop or click to browse'.
  2. Read the format chips inside the dropzone.
    - expect: The dropzone lists the following format chips in order: PDF, DOCX, JSON, CSV, XLSX, TXT, PNG, JPG, WAV, MP3, MP4.

### 2. navigation

**Seed:** `tests/seed.spec.ts`

#### 2.1. Top navigation moves between Home, Insights, and Explore

**File:** `tests/knowledge-mining/navigation-tabs.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/.
    - expect: The URL path is '/' and the 'Home' tab is active.
  2. Click the 'Insights' navigation item.
    - expect: The URL path changes to '/insights'.
    - expect: The main content area eventually shows the heading 'Unified Knowledge Insights' (a loading progressbar labeled 'Loading dashboard' may be shown first).
  3. Click the 'Explore' navigation item.
    - expect: The URL path changes to '/explore'.
    - expect: A record counter '10 records' and '10 ready sources' are visible in the Explore header.
    - expect: A 'Sources' section, a 'Filter dimensions' section, and an 'Ask your data' chat panel are all visible.
  4. Click the 'Home' navigation item.
    - expect: The URL path returns to '/'.
    - expect: The 'Telecom Analysis Dataset' summary card is visible again.

### 3. insights

**Seed:** `tests/seed.spec.ts`

#### 3.1. Insights dashboard renders Unified Knowledge Insights header and metadata

**File:** `tests/knowledge-mining/insights-header.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the 'Loading dashboard' progressbar to disappear.
    - expect: A level-1 heading 'Unified Knowledge Insights' is visible.
    - expect: The eyebrow label 'Insights overview' is visible above the heading.
    - expect: A metadata row shows 'Dataset:', 'Source: documents', and an 'Updated:' date.
  2. Observe the header actions.
    - expect: An 'Ask your data' button is visible in the top bar (this becomes visible once Insights loads and links to the Explore view).
    - expect: The 'Sign in' button remains visible in the top bar.

#### 3.2. Insights filter panel exposes scenario-specific dimensions and Clear all

**File:** `tests/knowledge-mining/insights-filters.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A 'Filter insights' block is visible with a 'Clear all' button.
  2. Enumerate the filter comboboxes in the 'Filter insights' block.
    - expect: Comboboxes are shown for at least the following dimensions: 'Year', 'Source Type', 'Organization Name Variant', 'Source', 'Type'.
    - expect: Each combobox defaults to the value 'All'.
  3. Open the 'Source Type' combobox.
    - expect: The dropdown includes options 'All', 'json', and 'wav' (the two source types present in the Telecom Analysis dataset).
  4. Select 'json' in the 'Source Type' combobox, then click 'Clear all'.
    - expect: After selection, the combobox value updates to 'json'.
    - expect: After 'Clear all', every combobox is restored to 'All'.

#### 3.3. Insights AI-layout section renders summary, KPI, topic intensity, and highlights blocks

**File:** `tests/knowledge-mining/insights-ai-layout.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section labeled 'AI layout' with the caption 'Dynamic blocks chosen by the model for this dataset.' is visible.
  2. Verify the blocks rendered inside 'AI layout'.
    - expect: A 'Summary' block is present and its body text is non-empty.
    - expect: A KPI block titled 'Total Support Interactions Analyzed' is present and shows the value '10'.
    - expect: A 'Topic intensity' block lists at least the topics 'factory reset', 'Voicemail and call forwarding setup', 'Upgrading phone plan due to website issues', 'Updating account mailing and email address', and 'Smartphone won't turn on troubleshooting'.
    - expect: A 'Relationship graph' block is present.
    - expect: A 'Timeline' block lists at least three patterns labeled 'Pattern 1', 'Pattern 2', 'Pattern 3'.
    - expect: A 'Topic vs entity signal' block shows 'Topics: 25' and 'Entities: 30'.
    - expect: A 'Key highlights' block lists at least four bullet items.

#### 3.4. Insights data overview shows scenario record and enrichment counts

**File:** `tests/knowledge-mining/insights-data-overview.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section labeled 'Data overview' is visible with the caption 'A quick snapshot of record count, extracted topics, entities, and links.'
  2. Read the four KPI tiles inside 'Data overview'.
    - expect: 'Records analyzed' tile shows the numeric value '10'.
    - expect: 'Topics identified' tile shows the numeric value '25'.
    - expect: 'Entities extracted' tile shows the numeric value '13'.
    - expect: 'Relationship links' tile shows the numeric value '3'.
    - expect: Each tile shows a short helper caption describing what it counts.

#### 3.5. Insights suggested explorations expose clickable, dataset-specific prompts

**File:** `tests/knowledge-mining/insights-suggested-explorations.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section titled 'Suggested explorations' with the caption 'Conversation-ready prompts to drill into AI findings.' is visible.
    - expect: The section contains at least six clickable prompt buttons, including 'How do the findings change by year?' and 'How do the findings change by source type?'.
    - expect: At least one prompt references dataset-specific fields such as 'interaction_type', 'resolution_status', 'source_type', or 'issue_type'.

#### 3.6. Insights AI findings cards show insight text, score, and tag chips

**File:** `tests/knowledge-mining/insights-ai-findings.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section titled 'AI findings' with the caption 'Ranked by impact score, confidence, and evidence.' is visible.
    - expect: A 'Document findings help' button is visible next to the section title.
  2. Inspect the first four AI-finding cards in the section.
    - expect: Each card shows a badge 'Insight' and a 'Score' value.
    - expect: Each card renders a non-empty body paragraph.
    - expect: Each card renders a footer with the source label 'Unified Knowledge Insights' and at least one hashtag chip (for example '#users', '#device', '#security', '#billing').

#### 3.7. Insights knowledge distribution shows Topic share ranking and Entity frequency chart

**File:** `tests/knowledge-mining/insights-knowledge-distribution.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section titled 'Knowledge distribution' with the caption 'See which topics dominate and which entities are mentioned most.' is visible.
  2. Inspect the 'Topic share' block.
    - expect: The 'Topic share' block shows the count '8' (top topics rendered) and includes 'factory reset' with '22.2%' as the leading topic.
    - expect: The block lists additional telecom topics such as 'Voicemail and call forwarding setup', 'Reporting and securing a lost phone', and 'Phone troubleshooting: freezing and battery drain', each showing a percentage.
  3. Inspect the 'Entity frequency' block.
    - expect: An 'Entity frequency' block is visible with the count '8' and a chart image (bar chart) rendered inside it.

#### 3.8. Insights unexpected patterns section lists AI-detected timeline shifts

**File:** `tests/knowledge-mining/insights-unexpected-patterns.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: A section titled 'Unexpected patterns' with the caption 'Timeline view of notable deviations and AI-detected shifts.' is visible.
    - expect: The section renders at least three cards labeled 'Pattern 1', 'Pattern 2', and 'Pattern 3'.
    - expect: Each pattern card renders a non-empty description and the shared dataset summary underneath.

### 4. explore

**Seed:** `tests/seed.spec.ts`

#### 4.1. Explore page loads sources, filter dimensions, and chat panel

**File:** `tests/knowledge-mining/explore-layout.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The Explore header shows '10 records' and '10 ready sources'.
    - expect: A 'History' button showing a numeric count in parentheses is visible in the header.
  2. Inspect the 'Sources' panel on the left.
    - expect: A 'Sources' button/label is visible.
    - expect: The list contains 10 items whose filenames begin with 'convo_' and end with '.wav' or '.json'.
    - expect: Each source row shows a numeric count badge (e.g. '1').
  3. Inspect the 'Filter dimensions' panel.
    - expect: A 'Filter dimensions' section is visible with the helper 'Use these to narrow records before asking questions'.
    - expect: The following filter buttons are all present with a numeric count in parentheses: 'Source Type', 'Topic', 'Document Type', 'Interaction Type', 'Resolution Status', 'Interaction Reason', 'Agent', 'Products Or Programs', 'Organization', 'Customer', 'Topics', 'Issue Type', 'Issue Category', 'Customer Intent', 'Account Number', 'Support Agent', 'Primary Service Area', 'Key Phrases', 'Entities'.
  4. Inspect the chat panel on the right.
    - expect: The chat panel shows the title 'Ask your data' and the subtitle 'Summaries, trends, and analysis — all through conversation.'
    - expect: A 'New conversation' button, a textarea with placeholder 'Ask a question...', and a 'Send' button (initially disabled) are visible.

#### 4.2. Explore filter dimension can be expanded to show scenario values with counts

**File:** `tests/knowledge-mining/explore-filter-expand.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The 'Source Type (2)' filter button is visible in the 'Filter dimensions' panel.
  2. Click 'Source Type (2)' to expand it.
    - expect: Two facet rows are shown under Source Type: 'wav' with count '5' and 'json' with count '5'.
  3. Click 'Interaction Type (7)' to expand it.
    - expect: Seven facet rows are shown under 'Interaction Type', each with a facet label and a numeric count.

#### 4.3. Selecting a source narrows the record counter

**File:** `tests/knowledge-mining/explore-source-selection.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The Explore header shows '10 records' initially.
  2. Click the source row whose filename begins with 'convo_03b0e193-5b55-42d3-a258-b0ff9336ae18'.
    - expect: The Explore header changes to show '1 selected' in place of the raw record count.
    - expect: A close ('x') affordance appears in the Sources panel to clear the selection.
  3. Click the close ('x') affordance to clear the source selection.
    - expect: The Explore header returns to showing '10 records'.

#### 4.4. History drawer lists past conversations with message counts

**File:** `tests/knowledge-mining/explore-history-drawer.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The 'History' button in the header shows a numeric count (e.g. 'History (7)' or higher).
  2. Click the 'History' button.
    - expect: A 'Chat History' drawer opens.
    - expect: The drawer shows a 'New conversation' action.
    - expect: The drawer lists at least one past conversation, each with a title and a message counter of the form 'N messages'.
    - expect: A close ('x') affordance is visible inside the drawer.
  3. Click the close ('x') affordance in the drawer.
    - expect: The 'Chat History' drawer closes and the Explore sources / filters / chat panels are visible again.

#### 4.5. 'New conversation' clears the chat input and starts a fresh session

**File:** `tests/knowledge-mining/explore-new-conversation.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore and type 'hello' into the 'Ask a question...' textarea (do NOT submit).
    - expect: The textarea contains the text 'hello'.
    - expect: The 'Send' button becomes enabled.
  2. Click 'New conversation'.
    - expect: The chat panel returns to its default state: title 'Ask your data', subtitle present, textarea empty, and 'Send' button disabled again.

### 5. chat-sample-questions

**Seed:** `tests/seed.spec.ts`

#### 5.1. Sample question 1: Total number of calls by date for last 7 days.

**File:** `tests/knowledge-mining/chat-total-calls-last-7-days.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The chat panel with the 'Ask a question...' textarea is visible.
    - expect: The 'History' button shows its current numeric count (e.g. 'History (N)').
  2. Type the verbatim sample question 'Total number of calls by date for last 7 days.' into the 'Ask a question...' textarea and press Enter (or click 'Send').
    - expect: The user question 'Total number of calls by date for last 7 days.' is echoed in the chat transcript.
    - expect: The assistant renders a response introduced by the phrase 'Total number of calls by date (last 7 days):'.
    - expect: The response contains a two-column table with headers 'Date (YYYY-MM-DD)' and 'Total calls'.
    - expect: At least one row of the table shows a total call count that is a positive integer (in the Telecom Analysis dataset this is '10' for the ingestion date).
    - expect: The AI disclaimer 'AI-generated content may be incorrect' is shown below the response.
  3. Observe the 'History' button counter.
    - expect: The counter shown in the 'History' button increases by 1 relative to its value before sending the question.

#### 5.2. Sample question 2: What are top 7 challenges user reported.

**File:** `tests/knowledge-mining/chat-top-7-challenges.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The chat panel with the 'Ask a question...' textarea is visible.
  2. Type the verbatim sample question 'What are top 7 challenges user reported.' into the 'Ask a question...' textarea and press Enter.
    - expect: The user question 'What are top 7 challenges user reported.' is echoed in the chat transcript.
    - expect: The assistant renders a response that lists challenges (a numbered or bulleted list, or a summary section labeled 'Top challenges').
    - expect: The response contains at least 3 distinct challenge entries.
    - expect: The response references at least one telecom-flavored topic observed in Insights, such as 'billing', 'lost phone', 'plan', 'device', or 'reset'.
    - expect: The AI disclaimer 'AI-generated content may be incorrect' is shown below the response.

#### 5.3. Sample question 3: What are the top recommendations to reduce these customer challenges?

**File:** `tests/knowledge-mining/chat-top-recommendations.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/explore.
    - expect: The chat panel with the 'Ask a question...' textarea is visible.
  2. First send the verbatim question 'What are top 7 challenges user reported.' and wait for its response, then send the follow-up verbatim question 'What are the top recommendations to reduce these customer challenges?' in the same conversation.
    - expect: Both questions are echoed in the chat transcript in the order they were sent.
    - expect: The follow-up response returns a set of recommendations (numbered or bulleted).
    - expect: The recommendations reference concrete themes seen in the dataset, such as self-service playbooks, security workflows (remote lock / device blocking), billing add-on monitoring, or website / plan-upgrade UX issues.
    - expect: The AI disclaimer 'AI-generated content may be incorrect' is shown below the response.

#### 5.4. Suggested exploration prompt from Insights triggers a chat response in Explore

**File:** `tests/knowledge-mining/chat-suggested-exploration.spec.ts`

**Steps:**
  1. Navigate to https://app-ckmmpoxx4d.azurewebsites.net/insights and wait for the dashboard to load.
    - expect: The 'Suggested explorations' section is visible.
  2. Click the suggested prompt button 'How does resolution_status vary by source_type (json vs wav)?'.
    - expect: The app navigates to the Explore chat surface (URL contains '/explore') OR the chat panel appears with the prompt pre-filled as the user question in the transcript.
    - expect: The assistant renders a response that references 'resolution_status', 'source_type', and at least one of 'json' or 'wav'.
    - expect: The AI disclaimer 'AI-generated content may be incorrect' is shown below the response.
