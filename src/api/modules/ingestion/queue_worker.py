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

    MAX_RETRIES = 3

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

    # Scale visibility timeout based on expected processing time
    _BASE_VISIBILITY_SEC = 600
    _MAX_VISIBILITY_SEC = 3600  # 1 hour max for very large files

    def _poll_loop(self, queue_name: str, handler):
        """Main polling loop for a single queue."""
        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=self._max_concurrent) as pool:
            while self._running:
                try:
                    messages = list(queue_service.receive(
                        queue_name,
                        max_messages=self._max_concurrent,
                        visibility_timeout=self._BASE_VISIBILITY_SEC,
                    ))

                    if not messages:
                        self._wait()
                        continue

                    futures = []
                    for msg in messages:
                        try:
                            payload = json.loads(msg.content)
                            futures.append(pool.submit(self._handle_with_retry, queue_name, handler, msg, payload))
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid message in {queue_name}, deleting")
                            queue_service.delete(queue_name, msg)

                    for f in futures:
                        try:
                            f.result()
                        except Exception as e:
                            logger.error(f"Worker error in {queue_name}: {e}")

                except Exception as e:
                    if not hasattr(self, '_consecutive_errors'):
                        self._consecutive_errors = {}
                    count = self._consecutive_errors.get(queue_name, 0) + 1
                    self._consecutive_errors[queue_name] = count
                    # Log first error, then only every 60th (~5 min at 5s interval)
                    if count == 1 or count % 60 == 0:
                        logger.error(f"Poll error for {queue_name} (x{count}): {e}")
                    # Back off: 5s → 30s max on persistent failures
                    import time
                    backoff = min(self._poll_interval * count, 30)
                    for _ in range(int(backoff * 10)):
                        if not self._running:
                            return
                        time.sleep(0.1)
                    continue

    def _handle_with_retry(self, queue_name: str, handler, msg, payload: dict):
        """Wrap a handler with exponential backoff retry logic."""
        import time
        retry_count = payload.get("_retry_count", 0)
        try:
            handler(msg, payload)
        except Exception as e:
            if retry_count < self.MAX_RETRIES:
                backoff = 2 ** retry_count  # 1s, 2s, 4s
                logger.warning(
                    f"[{queue_name}] Retrying ({retry_count + 1}/{self.MAX_RETRIES}) "
                    f"after {backoff}s for {payload.get('filename', 'unknown')}: {e}"
                )
                time.sleep(backoff)
                # Re-enqueue with incremented retry count
                payload["_retry_count"] = retry_count + 1
                queue_service.delete(queue_name, msg)
                queue_service.enqueue(queue_name, payload)
            else:
                logger.error(
                    f"[{queue_name}] Permanent failure after {self.MAX_RETRIES} retries "
                    f"for {payload.get('filename', 'unknown')}: {e}"
                )
                queue_service.delete(queue_name, msg)
                # Mark file as failed
                file_id = payload.get("file_id")
                if file_id:
                    from src.api.modules.ingestion.service import ingestion_service
                    ingestion_service._update_file_status(
                        file_id, "failed",
                        error=f"Failed after {self.MAX_RETRIES} retries: {e}"
                    )

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

            # Extract CU-enriched fields instead of discarding them
            cu_fields = {}
            if extracted.fields:
                if extracted.fields.get("summary", {}).get("valueString"):
                    cu_fields["summary"] = extracted.fields["summary"]["valueString"]
                if extracted.fields.get("topic", {}).get("valueString"):
                    cu_fields["topic"] = extracted.fields["topic"]["valueString"]
                if extracted.fields.get("keyPhrases", {}).get("valueString"):
                    cu_fields["key_phrases"] = [
                        kp.strip() for kp in extracted.fields["keyPhrases"]["valueString"].split(",")
                        if kp.strip()
                    ]

            base_metadata = {
                "source_file": filename,
                "source_type": ext,
                "page_count": str(extracted.page_count),
            }
            # Merge CU fields into metadata so they flow through the whole pipeline
            if cu_fields.get("summary"):
                base_metadata["summary"] = cu_fields["summary"]
            if cu_fields.get("topic"):
                base_metadata["topic"] = cu_fields["topic"]
            if cu_fields.get("key_phrases"):
                base_metadata["key_phrases"] = ", ".join(cu_fields["key_phrases"])

            # Save extracted document to ingestion service
            doc_data = {
                "id": file_id,
                "type": ext,
                "text": extracted.markdown,
                "metadata": base_metadata,
            }
            if cu_fields.get("summary"):
                doc_data["summary"] = cu_fields["summary"]
            if cu_fields.get("key_phrases"):
                doc_data["key_phrases"] = cu_fields["key_phrases"]
            if cu_fields.get("topic"):
                doc_data["topics"] = [cu_fields["topic"]]

            ingestion_service.load_json_data([doc_data], filename=filename)

            # Store extracted text in blob (avoids 64 KB queue message limit)
            text_blob_path = f"extracted/{file_id}/content.txt"
            try:
                container = blob_client.get_container_client(settings.azure_storage_container)
                tb = container.get_blob_client(text_blob_path)
                tb.upload_blob(extracted.markdown.encode("utf-8"), overwrite=True)
            except Exception as e:
                logger.error(f"[extraction] Failed to store extracted text for {filename}: {e}")
                raise

            if cu_fields:
                logger.info(f"[extraction] CU fields captured for {filename}: {list(cu_fields.keys())}")

            # Enqueue for Stage 2: enrichment (reference only, no inline text)
            enrichment_msg = {
                "file_id": file_id,
                "filename": filename,
                "ext": ext,
                "text_blob_path": text_blob_path,
                "text_length": len(extracted.markdown),
                "metadata": base_metadata,
                "cu_fields": cu_fields,
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
        metadata = payload.get("metadata", {})

        # Read text from blob (or inline for backwards-compat with old messages)
        text = payload.get("text", "")
        text_blob_path = payload.get("text_blob_path")
        if text_blob_path and not text:
            try:
                settings = get_settings()
                blob_client = azure_storage_service._get_blob_client()
                container = blob_client.get_container_client(settings.azure_storage_container)
                blob = container.get_blob_client(text_blob_path)
                text = blob.download_blob().readall().decode("utf-8")
            except Exception as e:
                logger.error(f"[enrichment] Failed to read extracted text for {filename}: {e}")
                raise

        # Extend visibility timeout for large documents
        text_length = payload.get("text_length", len(text))
        if text_length > 50_000:
            try:
                extra_sec = min(text_length // 1000, self._MAX_VISIBILITY_SEC - self._BASE_VISIBILITY_SEC)
                queue_service.update_visibility(ENRICHMENT_QUEUE, message, self._BASE_VISIBILITY_SEC + extra_sec)
            except Exception:
                pass  # Non-critical

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

            # Step 2: Generate embeddings (batched)
            embeddings_service = EmbeddingsService()
            settings = get_settings()

            embeddings = embeddings_service.generate_embeddings_batch(chunks)

            # Step 3: Index chunks + embeddings in Azure AI Search
            indexed = azure_storage_service.index_chunks(
                doc_id=file_id,
                chunks=chunks,
                embeddings=embeddings,
                metadata=metadata,
            )
            logger.info(f"[enrichment] {filename}: {indexed} chunks indexed")

            # Step 4: Run AI enrichment (summary, keywords, filters)
            cu_fields = payload.get("cu_fields", {})
            doc_data = {
                "id": file_id,
                "type": payload.get("ext", ""),
                "text": text,
                "metadata": metadata,
            }
            # Forward CU-extracted fields so _track_file can reuse them
            if cu_fields.get("summary"):
                doc_data["summary"] = cu_fields["summary"]
            if cu_fields.get("key_phrases"):
                doc_data["key_phrases"] = cu_fields["key_phrases"]
            if cu_fields.get("topic"):
                doc_data["topics"] = [cu_fields["topic"]]

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
