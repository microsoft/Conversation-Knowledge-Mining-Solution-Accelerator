"""External data sources module — connect to Fabric, SQL, Synapse, ODBC, or Azure AI Search.

Architecture:
- base.py        → BaseExternalDataSource ABC + config models
- registry.py    → DataSourceRegistry (CRUD, adapter factory, auto-detect, persistence)
- router.py      → FastAPI endpoints at /api/data-sources
- models.py      → API request/response models
- fabric.py      → Microsoft Fabric adapter
- sql.py         → Generic SQL adapter (PostgreSQL, MySQL, SQL Server)
- synapse.py     → Azure Synapse adapter
- odbc.py        → Generic ODBC/JDBC adapter
- azure_search.py → Azure AI Search adapter
"""
