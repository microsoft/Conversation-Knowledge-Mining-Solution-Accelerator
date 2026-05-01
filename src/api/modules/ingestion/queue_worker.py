"""Two-stage queue worker for document processing pipeline.

Stage 1 (Extraction): Blob → CU extraction → enqueue for enrichment
Stage 2 (Enrichment): Chunk → Embed → Index in Azure AI Search
"""

import io
import json
import logging
import threading

from src.api.config import get_settings
from src.api.modules.ingestion.queue_service import (
    queue_service, EXTRACTION_QUEUE, ENRICHMENT_QUEUE,
)

logger = logging.getLogger(__name__)


class QueueWorker:
    """Polls both queues and processes documents through the two-stage pipeline."""

    def __init__(self, poll_interval: int = 5, max_concurrent: int = 4):
        self._poll_interval = poll_interval
        self._max_concurrent = max_concurrent
        self._running = False
        self._threads: list[threading.Thread] = []

    def start(self):
        """Start worker threads for both pipeline stages."""
        if not queue_service.available:
            logger.info("Queue storage not available — queue worker disabled (using in-process fallback)")
            return

        if self._running:
            return

        self._running = True

        # Stage 1: Extraction worker
        t1 = threading.Thread(
            target=self._poll_loop,
            args=(EXTRACTION_QUEUE, self._handle_extraction),
            daemon=True,
            name="extraction-worker",
        )
        t1.start()
        self._threads.append(t1)

        # Stage 2: Enrichment worker
        t2 = threading.Thread(
            target=self._poll_loop,
            args=(ENRICHMENT_QUEUE, self._handle_enrichment),
            daemon=True,
            name="enrichment-worker",
        )
        t2.start()
        self._threads.append(t2)

        logger.info(f"Queue workers started (poll={self._poll_interval}s, workers={self._max_concurrent})")

    def stop(self):
        """Signal workers to stop."""
        self._running = False
        for t in self._threads:
            t.join(timeout=10)
        self._threads.clear()
        logger.info("Queue workers stopped")

    def _poll_loop(self, queue_name: str, handler):
        """Main polling loop for a single queue."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self._max_concurrent) as pool:
            while self._running:
                try:
                    messages = list(queue_service.receive(
                        queue_name,
                        max_messages=self._max_concurrent,
                        visibility_timeout=600,
                    ))

                    if not messages:
                        self._wait()
                        continue

                    futures = []
                    for msg in messages:
                        try:
                            payload = json.loads(msg.content)
                            futures.append(pool.submit(handler, msg, payload))
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid message in {queue_name}, deleting")
                            queue_service.delete(queue_name, msg)

                    for f in futures:
                        try:
                            f.result()
                        except Exception as e:
                            logger.error(f"Worker error in {queue_name}: {e}")

                except Exception as e:
                    logger.error(f"Poll error for {queue_name}: {e}")
                    self._wait()

    def _wait(self):
        """Sleep between polls, checking for stop signal."""
        import time
        for _ in range(self._poll_interval * 10):
            if not self._running:
                return
            time.sleep(0.1)

    # ── Stage 1: Extraction ──────────────────────────────────────

    def _handle_extraction(self, message, payload: dict):
        """Download raw file from blob → CU extraction → enqueue for enrichment."""
        from src.api.modules.ingestion.azure_storage import azure_storage_service
        from src.api.modules.document_intelligence.service import content_understanding_service
        from src.api.modules.ingestion.service import ingestion_service

        file_id = payload["file_id"]
        filename = payload["filename"]
        ext = payload["ext"]
        blob_path = payload["blob_path"]

        # Skip if already processed
        if ingestion_service.is_already_processed(file_id):
            logger.info(f"[extraction] Already processed, skipping: {filename}")
            queue_service.delete(EXTRACTION_QUEUE, message)
            return

        # Acquire lock to prevent concurrent processing
        if not ingestion_service.acquire_processing_lock(file_id):
            logger.info(f"[extraction] Already in progress, skipping: {filename}")
            return  # Message stays in queue, will retry after visibility timeout

        logger.info(f"[extraction] Processing: {filename}")

        try:
            # Download raw file from blob
            settings = get_settings()
            blob_client = azure_storage_service._get_blob_client()
            container = blob_client.get_container_client(settings.azure_storage_container)
            blob = container.get_blob_client(blob_path)
            content = blob.download_blob().readall()

            # Extract text via Content Understanding
            extracted = content_understanding_service.analyze(
                file=io.BytesIO(content), filename=filename
            )

            if not extracted.markdown.strip():
                ingestion_service._update_file_status(
                    file_id, "failed", error=f"No text could be extracted from {filename}"
                )
                queue_service.delete(EXTRACTION_QUEUE, message)
                return

            # Save extracted document to ingestion service
            doc_data = {
                "id": file_id,
                "type": ext,
                "text": extracted.markdown,
                "metadata": {
                    "source_file": filename,
                    "source_type": ext,
                    "page_count": str(extracted.page_count),
                },
            }
            ingestion_service.load_json_data([doc_data], filename=filename)

            # Enqueue for Stage 2: enrichment
            enrichment_msg = {
                "file_id": file_id,
                "filename": filename,
                "ext": ext,
                "text": extracted.markdown,
                "metadata": doc_data["metadata"],
            }
            queue_service.enqueue(ENRICHMENT_QUEUE, enrichment_msg)

            # Delete extraction message
            queue_service.delete(EXTRACTION_QUEUE, message)
            logger.info(f"[extraction] Complete, enqueued for enrichment: {filename}")

        except Exception as e:
            logger.error(f"[extraction] Failed for {filename}: {e}")
            ingestion_service._update_file_status(file_id, "failed", error=str(e))
        finally:
            ingestion_service.release_processing_lock(file_id)

    # ── Stage 2: Enrichment (Chunk → Embed → Index) ─────────────

    def _handle_enrichment(self, message, payload: dict):
        """Chunk text → generate embeddings → index in Azure AI Search."""
        from src.api.modules.ingestion.chunking import chunk_text
        from src.api.modules.embeddings.service import EmbeddingsService
        from src.api.modules.ingestion.azure_storage import azure_storage_service
        from src.api.modules.ingestion.service import ingestion_service

        file_id = payload["file_id"]
        filename = payload["filename"]
        text = payload["text"]
        metadata = payload.get("metadata", {})

        # Skip if already fully processed
        if ingestion_service.is_already_processed(file_id):
            logger.info(f"[enrichment] Already processed, skipping: {filename}")
            queue_service.delete(ENRICHMENT_QUEUE, message)
            return

        if not ingestion_service.acquire_processing_lock(file_id):
            logger.info(f"[enrichment] Already in progress, skipping: {filename}")
            return

        logger.info(f"[enrichment] Processing: {filename}")

        try:
            # Step 1: Chunk
            chunks = chunk_text(text)
            logger.info(f"[enrichment] {filename}: {len(chunks)} chunks")

            # Step 2: Generate embeddings
            embeddings_service = EmbeddingsService()
            embeddings: list[list[float]] = []
            settings = get_settings()

            for chunk in chunks:
                try:
                    emb = embeddings_service.generate_embedding(chunk)
                    embeddings.append(emb.embedding)
                except Exception as e:
                    logger.warning(f"[enrichment] Embedding failed for chunk: {e}")
                    embeddings.append([0.0] * 1536)  # Zero vector as fallback

            # Step 3: Index chunks + embeddings in Azure AI Search
            indexed = azure_storage_service.index_chunks(
                doc_id=file_id,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata,
            )
            logger.info(f"[enrichment] {filename}: {indexed} chunks indexed")

            # Step 4: Run AI enrichment (summary, keywords, filters)
            doc_data = {
                "id": file_id,
                "type": payload.get("ext", ""),
                "text": text,
                "metadata": metadata,
            }
            ingestion_service.finalize_ingestion([doc_data], filename)

            # Mark as ready
            ingestion_service._update_file_status(file_id, "ready")

            # Delete enrichment message
            queue_service.delete(ENRICHMENT_QUEUE, message)
            logger.info(f"[enrichment] Complete: {filename}")

        except Exception as e:
            logger.error(f"[enrichment] Failed for {filename}: {e}")
            ingestion_service._update_file_status(file_id, "failed", error=str(e))
        finally:
            ingestion_service.release_processing_lock(file_id)


queue_worker = QueueWorker()
