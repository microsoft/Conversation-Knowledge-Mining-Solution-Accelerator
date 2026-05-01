import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "/api";

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Fetch user info from EasyAuth and cache userId
let _userId: string | null = null;

async function getUserId(): Promise<string> {
  if (_userId) return _userId;
  const cached = localStorage.getItem("userId");
  if (cached) {
    _userId = cached;
    return cached;
  }
  try {
    const resp = await fetch(`${window.location.origin}/.auth/me`);
    if (resp.ok) {
      const data = await resp.json();
      const claims = data?.[0]?.user_claims || [];
      const oid = claims.find(
        (c: any) =>
          c.typ === "http://schemas.microsoft.com/identity/claims/objectidentifier" ||
          c.typ === "oid"
      );
      if (oid?.val) {
        _userId = oid.val;
        localStorage.setItem("userId", oid.val);
        return oid.val;
      }
    }
  } catch {
    // EasyAuth not available (local dev)
  }
  return "default";
}

// Attach userId header to every request
apiClient.interceptors.request.use(async (config) => {
  const userId = await getUserId();
  if (userId) {
    config.headers["X-Ms-Client-Principal-Id"] = userId;
  }
  return config;
});

// --- Ingestion ---
export const loadDefaultDataset = () => apiClient.post("/ingestion/load-default");
export const getDocuments = (params?: Record<string, string>) =>
  apiClient.get("/ingestion/documents", { params });
export const getDocument = (id: string) => apiClient.get(`/ingestion/documents/${id}`);
export const getIngestionStats = () => apiClient.get("/ingestion/stats");
export const getAvailableFilters = () => apiClient.get("/ingestion/filters");
export const getUploadedFiles = () => apiClient.get("/ingestion/files");
export const deleteFile = (fileId: string) =>
  apiClient.delete(`/ingestion/files/${encodeURIComponent(fileId)}`);
export const getExtractionInfo = () => apiClient.get("/ingestion/extraction");

// --- File Upload ---
export const uploadJsonFile = (file: File) => {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post("/ingestion/upload/json", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};
export const uploadDocument = (files: File | File[]) => {
  const formData = new FormData();
  const fileArray = Array.isArray(files) ? files : [files];
  fileArray.forEach((f) => formData.append("files", f));
  return apiClient.post("/ingestion/upload/document", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: 60000,
  });
};

// --- Content Understanding ---
export const extractDocument = (file: File, analyzer = "prebuilt-document") => {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.post(`/documents/extract?analyzer=${encodeURIComponent(analyzer)}`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

// --- Embeddings ---
export const indexDocuments = (docId?: string) =>
  apiClient.post("/embeddings/index", { doc_id: docId });
export const vectorSearch = (query: string, topK = 5, filters?: Record<string, string>) =>
  apiClient.post("/embeddings/search", { query, top_k: topK, filters });
export const getVectorStats = () => apiClient.get("/embeddings/stats");

// --- RAG ---
export const saveChatHistory = (
  sessionId: string,
  messages: Array<{ role: string; content: string; sources?: any[] }>,
  userId = "default",
  title?: string
) =>
  apiClient.post("/rag/chat/save", { session_id: sessionId, messages, user_id: userId, title });
export const loadChatHistory = (sessionId: string) =>
  apiClient.get(`/rag/chat/load/${sessionId}`);
export const listChatSessions = (userId = "default") =>
  apiClient.get("/rag/chat/sessions", { params: { user_id: userId } });
export const deleteChatSession = (sessionId: string, userId = "default") =>
  apiClient.delete(`/rag/chat/session/${sessionId}`, { params: { user_id: userId } });
export const askQuestion = (
  question: string,
  topK = 5,
  filters?: Record<string, string>,
  chatScope: "all" | "documents" = "all",
  documentIds?: string[]
) =>
  apiClient.post("/rag/ask", {
    question,
    top_k: topK,
    filters,
    include_sources: true,
    chat_scope: chatScope,
    document_ids: documentIds,
  });
export const sendConversation = (
  messages: { role: string; content: string }[],
  topK = 5,
  filters?: Record<string, string>,
  chatScope: "all" | "documents" = "all",
  documentIds?: string[]
) =>
  apiClient.post("/rag/conversation", {
    messages,
    top_k: topK,
    filters,
    chat_scope: chatScope,
    document_ids: documentIds,
  });

// --- Processing ---
export const summarizeText = (text: string, maxLength = 200, style = "concise") =>
  apiClient.post("/processing/summarize", { text, max_length: maxLength, style });
export const extractEntities = (text: string, entityTypes?: string[]) =>
  apiClient.post("/processing/extract-entities", { text, entity_types: entityTypes });
export const batchProcess = (docIds?: string[], operations = ["summarize"]) =>
  apiClient.post("/processing/batch", { doc_ids: docIds, operations });
export const getInsights = (fileIds?: string[], externalIndexId?: string, dataSourceId?: string, refresh = false) =>
  apiClient.get("/processing/insights", {
    params: {
      ...(fileIds ? { file_ids: fileIds.join(",") } : {}),
      ...(externalIndexId ? { external_index_id: externalIndexId } : {}),
      ...(dataSourceId ? { data_source_id: dataSourceId } : {}),
      ...(refresh ? { refresh: true } : {}),
    },
  });
export const getCachedInsights = () => apiClient.get("/processing/insights/cached");

// --- Pipelines ---
export const listPipelines = (source?: string) =>
  apiClient.get("/pipelines/", { params: source ? { source } : undefined });
export const getPipelineRegistry = () => apiClient.get("/pipelines/registry");
export const getRunHistory = (limit = 20) =>
  apiClient.get("/pipelines/history", { params: { limit } });
export const runPipeline = (pipelineName: string, parameters?: Record<string, unknown>) =>
  apiClient.post("/pipelines/run", { pipeline_name: pipelineName, parameters });
export const validatePipelineYaml = (yamlContent: string) =>
  apiClient.post("/pipelines/validate", { yaml_content: yamlContent });
export const uploadPipeline = (yamlContent: string) =>
  apiClient.post("/pipelines/upload", { yaml_content: yamlContent });
export const generatePipelineConfig = (name?: string, docTypes?: string[]) =>
  apiClient.post("/pipelines/generate", { name, doc_types: docTypes });
export const getAutoConfig = () => apiClient.get("/pipelines/automation/config");
export const setAutoConfig = (enabled: boolean, defaultPipeline: string, autoSelect = true) =>
  apiClient.put("/pipelines/automation/config", { enabled, default_pipeline: defaultPipeline, auto_select: autoSelect });
export const getProcessingStatus = () => apiClient.get("/pipelines/status");

// --- External Data Sources ---
export const getDataSourceTypes = () => apiClient.get("/data-sources/types");
export const listDataSources = () => apiClient.get("/data-sources/");
export const createDataSource = (data: {
  name: string;
  source_type: string;
  connection_string?: string;
  endpoint?: string;
  database?: string;
  table_or_query?: string;
  auth_method?: string;
  field_mapping?: {
    id_field?: string;
    text_field?: string;
    title_field?: string;
    type_field?: string;
    timestamp_field?: string;
    metadata_fields?: Record<string, string>;
  };
  query_mode?: string;
}) => apiClient.post("/data-sources/", data);
export const updateDataSource = (id: string, data: Record<string, unknown>) =>
  apiClient.put(`/data-sources/${encodeURIComponent(id)}`, data);
export const deleteDataSource = (id: string) =>
  apiClient.delete(`/data-sources/${encodeURIComponent(id)}`);
export const testDataSourceConnection = (data: {
  source_type: string;
  connection_string?: string;
  endpoint?: string;
  database?: string;
  table_or_query?: string;
  auth_method?: string;
}) => apiClient.post("/data-sources/test", data);
export const testExistingDataSource = (id: string) =>
  apiClient.post(`/data-sources/${encodeURIComponent(id)}/test`);
export const getDataSourceSchema = (id: string) =>
  apiClient.get(`/data-sources/${encodeURIComponent(id)}/schema`);
export const getDataSourceSample = (id: string, count = 10) =>
  apiClient.get(`/data-sources/${encodeURIComponent(id)}/sample`, { params: { count } });
export const ingestDataSource = (id: string) =>
  apiClient.post(`/data-sources/${encodeURIComponent(id)}/ingest`);
export const quickConnectDataSource = (data: {
  name: string;
  source_type: string;
  connection_string?: string;
  endpoint?: string;
  database?: string;
  table_or_query: string;
  auth_method?: string;
  field_mapping?: {
    id_field?: string;
    text_field?: string;
    title_field?: string;
    type_field?: string;
    timestamp_field?: string;
    metadata_fields?: Record<string, string>;
  };
  query_mode?: string;
}) => apiClient.post("/data-sources/quick-connect", data);

export default apiClient;
