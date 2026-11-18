# Local SQLite for business data and graph position

Accepted design. Use separate SQLite files for the application and LangGraph checkpoints. The business database owns the request state and audit history. The checkpoint identifies the position to resume. WAL mode and short version-checked transactions support the local workflow. Startup recovery reconciles the two stores after a crash. Multi-host deployment would require a shared database and a worker.
