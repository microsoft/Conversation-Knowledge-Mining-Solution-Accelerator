from backend.storage.base import BasePipelineStore


class InMemoryPipelineStore(BasePipelineStore):
    def __init__(self):
        self._runs: list[dict] = []

    def save_run(self, run: dict) -> None:
        self._runs.append(run)

    def get_runs(self, limit: int = 20) -> list[dict]:
        return self._runs[-limit:]


pipeline_store = InMemoryPipelineStore()
