# Plan: External Data Source Support (Fabric, SQL, Synapse, ODBC/JDBC)

## TL;DR
Users with data in Microsoft Fabric, generic SQL databases, Azure Synapse, or any ODBC/JDBC-compatible database can connect to the accelerator without migrating their data. The system supports two integration patterns: **Pull & Ingest** (import data into the accelerator's search index) and **Live Query** (query external DB directly at RAG time). Users configure field mappings via UI or API. A new frontend Settings page lets users manage data source connections.

---

## Phase 1: Backend — Data Source Abstraction Layer

### Step 1: Define `BaseExternalDataSource` interface
- Create `backend/modules/data_sources/base.py`
- ABC with methods: `connect(config)`, `disconnect()`, `test_connection()`, `search(query, top_k, filters) -> list[dict]`, `sample(count) -> list[dict]`, `fetch_all(batch_size) -> Iterator[list[dict]]`, `get_schema() -> dict` (returns column names/types for mapping UI)
- Define `DataSourceConfig` pydantic model: `id`, `name`, `source_type` (enum: fabric, sql, synapse, odbc, azure_search), `connection_string`, `endpoint`, `database`, `table_or_query`, `auth_method` (enum: connection_string, managed_identity, entra_id), `field_mapping` (dict mapping accelerator fields → source columns)
- Define `FieldMapping` model: `text_field`, `id_field`, `title_field`, `type_field`, `metadata_fields: dict[str, str]`, `timestamp_field`

### Step 2: Implement concrete data source adapters
Each adapter implements `BaseExternalDataSource`:

- **`FabricDataSource`** (`backend/modules/data_sources/fabric.py`)
  - Uses `pyodbc` with Fabric SQL endpoint or Microsoft Fabric REST API
  - Auth via Entra ID token (DefaultAzureCredential)
  - `search()` translates to SQL `WHERE ... LIKE` or full-text search
  - `fetch_all()` paginates with `OFFSET/FETCH`

- **`SqlDataSource`** (`backend/modules/data_sources/sql.py`)
  - Uses `pyodbc` for generic SQL (PostgreSQL, MySQL, SQL Server)
  - Connection string-based auth
  - Supports custom SQL query or table name

- **`SynapseDataSource`** (`backend/modules/data_sources/synapse.py`)
  - Uses `pyodbc` with Synapse SQL endpoint
  - Auth via Entra ID token
  - Supports serverless and dedicated SQL pools

- **`OdbcDataSource`** (`backend/modules/data_sources/odbc.py`)
  - Generic ODBC/JDBC wrapper
  - User provides full connection string + driver name

- **Refactor existing `ExternalIndexService`** → `AzureSearchDataSource` adapter
  - Move logic from `backend/modules/ingestion/external_index.py` into `backend/modules/data_sources/azure_search.py`
  - Implement same `BaseExternalDataSource` interface
  - Keep backward compatibility via thin wrapper in `external_index.py`

### Step 3: Data Source Registry & Persistence
- Create `backend/modules/data_sources/registry.py`
  - `DataSourceRegistry` class: manages registered adapters by `source_type`
  - CRUD for data source connections (stored in Azure SQL, not in-memory like current `ExternalIndexService`)
  - `get_adapter(source_id) -> BaseExternalDataSource` — factory method
- Create `backend/modules/data_sources/models.py` — Pydantic request/response models
- Persist configs to Azure SQL via new table `external_data_sources` (id, name, source_type, config_json, field_mapping_json, status, created_at, updated_at)

### Step 4: Data Source Router (API endpoints)
- Create `backend/modules/data_sources/router.py`
- Mount at `/api/data-sources` in `main.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | List all configured data sources |
| `/` | POST | Add new data source connection |
| `/{id}` | GET | Get data source details |
| `/{id}` | PUT | Update data source config/mapping |
| `/{id}` | DELETE | Remove data source |
| `/{id}/test` | POST | Test connection (returns success + row count) |
| `/{id}/schema` | GET | Fetch column names/types for mapping UI |
| `/{id}/sample` | GET | Sample rows (for preview in UI) |
| `/{id}/ingest` | POST | Pull & Ingest: import data into accelerator |
| `/types` | GET | List supported source types with config schemas |

---

## Phase 2: Backend — Integration Patterns

### Step 5: Pull & Ingest pattern (*depends on Steps 1-4*)
- Add `DataSourceIngestionService` in `backend/modules/data_sources/ingestion.py`
- `ingest(source_id, batch_size=1000)`:
  1. Call adapter's `fetch_all()` to iterate batches
  2. Apply `field_mapping` to transform rows → `Document` objects
  3. Feed into existing `IngestionService.load_json_data()` pipeline
  4. Track as a file via `_track_file()` for AI enrichment
  5. Persist to Azure Search index via `AzureStorageService`
- Support incremental sync: store `last_sync_timestamp` per source, filter by timestamp field on subsequent runs

### Step 6: Live Query pattern (*depends on Steps 1-4*)
- Modify `backend/modules/rag/service.py`:
  - Add `_search_external_data_source(source_id, query, top_k)` method
  - In `answer()`, check if active data sources are configured for live query
  - Route to appropriate adapter's `search()` method
  - Normalize results through `field_mapping` to match expected RAG context format
- Add `query_mode` field to `DataSourceConfig`: `"ingest"` | `"live"` | `"both"`

### Step 7: Processing & Insights for external sources (*depends on Steps 5-6*)
- Modify `backend/modules/processing/service.py`:
  - `generate_insights()` accepts `data_source_id` param (in addition to existing `external_index_id`)
  - Fetches sample documents via adapter, generates insights via LLM
- Update `backend/modules/processing/router.py` — add `data_source_id` query param

---

## Phase 3: Backend — Config & Settings

### Step 8: Config settings (*parallel with Phase 2*)
- Add to `backend/config.py`:
  - `enable_external_data_sources: bool = True`
  - `external_data_source_default_batch_size: int = 1000`
  - `external_data_source_timeout: int = 60`
- Add to `.env` template: corresponding env vars

### Step 9: SQL schema for data sources (*depends on Step 3*)
- Add to `backend/storage/sql_service.py`:
  - `_ensure_data_sources_table()` — creates `external_data_sources` table
  - `save_data_source(config)`, `get_data_source(id)`, `list_data_sources()`, `delete_data_source(id)`, `update_data_source(id, config)`
- Call `_ensure_data_sources_table()` in `_ensure_tables()` startup

---

## Phase 4: Frontend — Data Sources Settings Page

### Step 10: API client extensions (*parallel with Phase 2*)
- Add to `frontend/src/api/client.ts`:
  - `dataSources.list()`, `dataSources.create(config)`, `dataSources.update(id, config)`, `dataSources.delete(id)`, `dataSources.test(id)`, `dataSources.getSchema(id)`, `dataSources.sample(id)`, `dataSources.ingest(id)`, `dataSources.getTypes()`

### Step 11: Data Sources Settings page
- Create `frontend/src/pages/DataSources/DataSources.tsx` — main settings page
- Create `frontend/src/pages/DataSources/DataSources.css` — styles (per user preference: separate CSS)
- Sections:
  1. **Connected Sources** — list/table of configured data sources with status, last sync, actions (edit, test, delete, sync)
  2. **Add New Source** — wizard/dialog flow:
     - Step 1: Select source type (Fabric, SQL, Synapse, ODBC, Azure AI Search)
     - Step 2: Enter connection details (dynamic form based on source type)
     - Step 3: Test connection → show row count
     - Step 4: Field mapping — auto-detect columns via `/schema`, user maps to accelerator fields (text, id, title, metadata) with dropdowns
     - Step 5: Choose query mode (Pull & Ingest vs Live Query vs Both)
     - Step 6: Preview sample data → Confirm

- Use Fluent UI components (per user preference): `DataGrid`, `Dialog`, `Dropdown`, `Button`, `Field`, `Input`, `Badge` for status

### Step 12: Add route and navigation (*depends on Step 11*)
- Add `/settings/data-sources` route in `App.tsx`
- Add "Data Sources" nav item to `Layout` component (sidebar/header)
- Optionally add a "Connect Data Source" card on the Home page alongside existing "Connect External Index"

### Step 13: Integrate with Explore page (*depends on Steps 6, 11*)
- On `/explore` page, show external data sources in the file/source selector
- When user selects an external source, RAG queries route through live query path
- Display source attribution in chat responses (which data source answered)

---

## Phase 5: Migration & Backward Compatibility

### Step 14: Migrate existing ExternalIndexService (*depends on Steps 2-3*)
- Wrap existing `ExternalIndexService` endpoints to delegate to new `DataSourceRegistry` + `AzureSearchDataSource`
- Keep existing `/api/ingestion/external/*` endpoints working (deprecate but don't remove)
- Map existing frontend calls to new backend (or keep old endpoints as thin proxies)

---

## Relevant Files

**New files to create:**
- `backend/modules/data_sources/__init__.py` — module init
- `backend/modules/data_sources/base.py` — `BaseExternalDataSource` ABC, `DataSourceConfig`, `FieldMapping`
- `backend/modules/data_sources/registry.py` — `DataSourceRegistry` class
- `backend/modules/data_sources/models.py` — API request/response models
- `backend/modules/data_sources/router.py` — FastAPI router at `/api/data-sources`
- `backend/modules/data_sources/ingestion.py` — Pull & Ingest service
- `backend/modules/data_sources/fabric.py` — `FabricDataSource` adapter
- `backend/modules/data_sources/sql.py` — `SqlDataSource` adapter
- `backend/modules/data_sources/synapse.py` — `SynapseDataSource` adapter
- `backend/modules/data_sources/odbc.py` — `OdbcDataSource` adapter
- `backend/modules/data_sources/azure_search.py` — refactored from `ExternalIndexService`
- `frontend/src/pages/DataSources/DataSources.tsx` — settings page
- `frontend/src/pages/DataSources/DataSources.css` — styles

**Existing files to modify:**
- `backend/app/main.py` — register new `/api/data-sources` router
- `backend/config.py` — add external data source settings
- `backend/modules/rag/service.py` — add `_search_external_data_source()`, modify `answer()` dispatch
- `backend/modules/processing/service.py` — support `data_source_id` in insights
- `backend/modules/processing/router.py` — add `data_source_id` param
- `backend/storage/sql_service.py` — add `external_data_sources` table + CRUD
- `backend/modules/ingestion/external_index.py` — deprecate, delegate to new system
- `frontend/src/api/client.ts` — add data source API methods
- `frontend/src/App.tsx` — add `/settings/data-sources` route
- `frontend/src/components/Layout.tsx` — add nav item
- `frontend/src/pages/Explore/` — show external sources in source selector
- `backend/app/requirements.txt` — add `pyodbc` (if not present)

**Reference files (patterns to reuse):**
- `backend/modules/ingestion/external_index.py` — existing `ExternalIndexService` pattern for `AzureSearchDataSource`
- `backend/storage/base.py` — ABC pattern for `BaseExternalDataSource`
- `backend/modules/ingestion/service.py` — `load_json_data()` for Pull & Ingest integration
- `backend/modules/rag/service.py` — `_answer_from_external()` for Live Query pattern
- `backend/storage/sql_service.py` — `_ensure_tables()` pattern for new SQL table

---

## Verification

1. **Unit tests**: Test each adapter with mock connections — verify `connect()`, `search()`, `fetch_all()`, `get_schema()` return correct shapes
2. **Integration test — Pull & Ingest**: Configure a SQL data source → ingest → verify docs appear in search index → RAG query returns results from ingested data
3. **Integration test — Live Query**: Configure a data source in live mode → RAG query → verify results come from external DB in real-time
4. **API test**: Hit all `/api/data-sources/*` endpoints via curl/Postman — verify CRUD, test connection, schema fetch, sample data
5. **Frontend test**: Walk through the Add Data Source wizard end-to-end in the browser — verify form validation, connection test feedback, field mapping dropdown population, sample preview
6. **Backward compatibility**: Existing `/api/ingestion/external/connect` still works → verify old ExternalIndex flow is unbroken
7. **Security**: Verify connection strings are not returned in API responses (masked), credentials stored encrypted or via managed identity only

---

## Decisions

- **Adapter pattern** over monolithic service — each data source type gets its own adapter class behind a common interface, making it easy to add new sources later
- **SQL persistence** for data source configs (not in-memory like current ExternalIndexService) — configs survive restarts
- **Field mapping at config time** — users set up column-to-field mapping once, applied automatically during ingestion and live queries
- **Existing ExternalIndexService preserved** as backward-compatible wrapper — no breaking changes to current frontend
- **pyodbc as the common driver** for Fabric, SQL, Synapse, and generic ODBC — single dependency covers all SQL-based sources
- **Separate CSS files** and **Fluent UI components** per user preferences
- **Connection strings stored securely** — never returned in full via API, masked in UI

## Further Considerations

1. **Scheduled sync for Pull & Ingest**: Should we support automatic periodic re-sync (e.g., every N hours)? Recommend deferring to a follow-up — manual "Sync Now" button is sufficient for v1.
2. **Fabric OneLake direct access**: Beyond SQL endpoint, Fabric data can be accessed via OneLake file API (Parquet/Delta). This would require a separate `OneLakeDataSource` adapter. Recommend starting with SQL endpoint only.
3. **Connection string security**: For production, connection strings should be stored in Azure Key Vault rather than SQL. Recommend Key Vault integration as a fast-follow.
