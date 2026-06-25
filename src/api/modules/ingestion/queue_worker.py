"""Two-stage queue worker for document processing pipeline.

Stage 1 (Extraction): Blob → CU extraction → enqueue for enrichment
Stage 2 (Enrichment): Chunk → Embed → Index in Azure AI Search
"""

import io
import json
import logging
import threading

from azure.core.exceptions import ResourceNotFoundError

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
            queue_service.delete(EXTRACTION_QUEUE, message)
            return

        # Acquire lock to prevent concurrent processing
        if not ingestion_service.acquire_processing_lock(file_id):
            return  # Message stays in queue, will retry after visibility timeout

        cu_wait_sec = None
        content_size = None

        try:
            # Download raw file from blob
            settings = get_settings()
            blob_client = azure_storage_service._get_blob_client()
            container = blob_client.get_container_client(settings.azure_storage_container)
            blob = container.get_blob_client(blob_path)
            content = blob.download_blob().readall()
            content_size = len(content)

            # ── Phase 1: Fast local extraction ──────────────────────────────
            # Try to extract text without CU for native-text files.
            # This makes native PDFs, DOCX, TXT, XLSX chateable in seconds.
            from src.api.modules.ingestion.local_extractor import extract_text as local_extract
            try:
                local_text, needs_cu = local_extract(content, filename)
            except ValueError as ve:
                # Format validation error (e.g., WAV not supported) — terminal failure
                error_msg = str(ve)
                logger.error(f"[extraction] {error_msg}")
                ingestion_service._update_file_status(file_id, "failed", error=error_msg)
                queue_service.delete(EXTRACTION_QUEUE, message)
                ingestion_service.release_processing_lock(file_id)
                return
            except Exception as e:
                error_msg = f"Local text extraction failed for {filename}: {e}"
                logger.warning(f"[extraction] {error_msg} — will try CU analysis")
                local_text = ""
                needs_cu = True

            text_blob_path = f"extracted/{file_id}/content.txt"

            if local_text.strip():
                # Store text blob immediately
                try:
                    tb = container.get_blob_client(text_blob_path)
                    tb.upload_blob(local_text.encode("utf-8"), overwrite=True)
                except Exception as e:
                    logger.error(f"[extraction] Failed to store locally extracted text for {filename}: {e}")
                    raise

                # Register document in ingestion service so chat can find it
                base_metadata = {
                    "source_file": filename,
                    "source_type": ext,
                    "page_count": "0",  # unknown until CU
                }
                doc_data = {"id": file_id, "type": ext, "text": local_text, "metadata": base_metadata}
                ingestion_service.load_json_data([doc_data], filename=filename)

                # Mark as "extracted" — immediately available for chat
                ingestion_service._update_file_status(file_id, "extracted")

                if not needs_cu:
                    # Native file — skip CU extraction entirely, go straight to enrichment
                    enrichment_msg = {
                        "file_id": file_id,
                        "filename": filename,
                        "ext": ext,
                        "text_blob_path": text_blob_path,
                        "text_length": len(local_text),
                        "metadata": base_metadata,
                        "cu_fields": {},
                    }
                    queue_service.enqueue(ENRICHMENT_QUEUE, enrichment_msg)
                    queue_service.delete(EXTRACTION_QUEUE, message)
                    logger.debug(f"[extraction] {filename} enqueued for enrichment (native format)")
                    return
                # else: scanned PDF — fall through to CU OCR below, keeping extracted status

            # ── Phase 2: CU extraction (scanned PDFs, images, audio) ────────
            cu_wait_sec = content_understanding_service.resolve_max_wait(content_size, settings.cu_poll_max_wait_sec)

            # Prefer SAS URL analysis to avoid re-uploading bytes to CU; fallback to bytes on failure.
            extracted = None
            sas_url = None
            if settings.cu_use_sas_url:
                try:
                    sas_url = azure_storage_service.get_raw_file_sas_url(file_id, filename)
                except Exception as e:
                    logger.warning(f"[extraction] Could not generate SAS URL for {filename}, using byte upload: {e}")

            if sas_url:
                try:
                    extracted = content_understanding_service.analyze_url(
                        file_url=sas_url,
                        filename=filename,
                        max_wait_sec=cu_wait_sec,
                    )
                except Exception as e:
                    logger.warning(f"[extraction] SAS URL CU analysis failed for {filename}, falling back to bytes: {e}")

            if extracted is None:
                extracted = content_understanding_service.analyze(
                    file=io.BytesIO(content),
                    filename=filename,
                    max_wait_sec=cu_wait_sec,
                )

            # If CU returned empty markdown, fall back to local text if available
            if not extracted.markdown.strip():
                if local_text.strip():
                    # Use locally extracted text as fallback when CU OCR returns nothing
                    logger.warning(
                        f"[extraction] CU extraction returned empty markdown for {filename}; "
                        f"falling back to {len(local_text)} chars of locally extracted text"
                    )
                    extracted.markdown = local_text
                else:
                    # No local text and no CU extraction — file is genuinely empty
                    error_msg = f"No text could be extracted from {filename} (CU returned empty markdown and no local text)"
                    logger.warning(f"[extraction] {error_msg}")
                    ingestion_service._update_file_status(
                        file_id, "failed", error=error_msg
                    )
                    queue_service.delete(EXTRACTION_QUEUE, message)
                    return

            # Extract CU-enriched fields instead of discarding them
            cu_fields = {}
            if extracted.fields:
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
            if cu_fields.get("topic"):
                base_metadata["topics"] = [cu_fields["topic"]]
            if cu_fields.get("key_phrases"):
                base_metadata["key_phrases"] = cu_fields["key_phrases"]

            # Save extracted document to ingestion service
            doc_data = {
                "id": file_id,
                "type": ext,
                "text": extracted.markdown,
                "metadata": base_metadata,
            }
            if cu_fields.get("key_phrases"):
                doc_data["key_phrases"] = cu_fields["key_phrases"]
            if cu_fields.get("topic"):
                doc_data["topics"] = [cu_fields["topic"]]

            ingestion_service.load_json_data([doc_data], filename=filename)

            # Store extracted text in blob (avoids 64 KB queue message limit)
            try:
                tb = container.get_blob_client(text_blob_path)
                tb.upload_blob(extracted.markdown.encode("utf-8"), overwrite=True)
            except Exception as e:
                logger.error(f"[extraction] Failed to store extracted text for {filename}: {e}")
                raise

            # Mark as extracted — now available for chat even before chunking/indexing
            ingestion_service._update_file_status(file_id, "extracted")

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

        except TimeoutError:
            # For large scanned files, go straight to full configured cap on retry.
            retry_wait_sec = settings.cu_poll_max_wait_sec

            if cu_wait_sec and retry_wait_sec > cu_wait_sec:
                logger.warning(
                    f"[extraction] Initial CU timeout for {filename} at {cu_wait_sec}s; retrying once with {retry_wait_sec}s"
                )
                try:
                    # Retry once with a longer wait using byte upload for deterministic retry path.
                    extracted = content_understanding_service.analyze(
                        file=io.BytesIO(content),
                        filename=filename,
                        max_wait_sec=retry_wait_sec,
                    )

                    if not extracted.markdown.strip():
                        # Fall back to local text if CU retry also returns empty
                        if local_text.strip():
                            logger.warning(
                                f"[extraction] CU retry also returned empty markdown for {filename}; "
                                f"falling back to {len(local_text)} chars of locally extracted text"
                            )
                            extracted.markdown = local_text
                        else:
                            error_msg = f"No text could be extracted from {filename} after CU retry and no local text available"
                            logger.error(f"[extraction] {error_msg}")
                            ingestion_service._update_file_status(file_id, "failed", error=error_msg)
                            return

                    cu_fields = {}
                    if extracted.fields:
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
                    if cu_fields.get("topic"):
                        base_metadata["topics"] = [cu_fields["topic"]]
                    if cu_fields.get("key_phrases"):
                        base_metadata["key_phrases"] = cu_fields["key_phrases"]

                    doc_data = {
                        "id": file_id,
                        "type": ext,
                        "text": extracted.markdown,
                        "metadata": base_metadata,
                    }
                    if cu_fields.get("key_phrases"):
                        doc_data["key_phrases"] = cu_fields["key_phrases"]
                    if cu_fields.get("topic"):
                        doc_data["topics"] = [cu_fields["topic"]]

                    ingestion_service.load_json_data([doc_data], filename=filename)

                    text_blob_path = f"extracted/{file_id}/content.txt"
                    container = blob_client.get_container_client(settings.azure_storage_container)
                    tb = container.get_blob_client(text_blob_path)
                    tb.upload_blob(extracted.markdown.encode("utf-8"), overwrite=True)

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
                    queue_service.delete(EXTRACTION_QUEUE, message)
                    return
                except TimeoutError:
                    pass
                except Exception as e:
                    logger.error(f"[extraction] Retry failed for {filename}: {e}")

            error_msg = (
                f"CU extraction timeout after {cu_wait_sec}s"
                f" (retry attempted up to {retry_wait_sec}s)"
                f" for {content_size} bytes: {filename}"
            )
            logger.error(f"[extraction] {error_msg}")
            ingestion_service._update_file_status(file_id, "failed", error=error_msg)
            queue_service.delete(EXTRACTION_QUEUE, message)
        except ResourceNotFoundError:
            # Raw blob is missing (deleted/moved/mismatched path). This is terminal for this message.
            error_msg = f"Source file not found in blob storage for {filename} ({blob_path})"
            logger.error(f"[extraction] {error_msg}")
            ingestion_service._update_file_status(file_id, "failed", error=error_msg)
            queue_service.delete(EXTRACTION_QUEUE, message)
        except ValueError as e:
            # Unsupported file type or parsing error
            error_msg = f"Invalid file format or parsing error: {str(e)}"
            logger.error(f"[extraction] {error_msg}")
            ingestion_service._update_file_status(file_id, "failed", error=error_msg)
            queue_service.delete(EXTRACTION_QUEUE, message)
        except Exception as e:
            import traceback
            error_msg = f"Extraction failed: {str(e)}"
            tb = traceback.format_exc()
            logger.error(f"[extraction] {error_msg}\n{tb}")
            # Provide detailed error context to user
            detailed_error = f"{error_msg} (See logs for details. File: {filename})"
            ingestion_service._update_file_status(file_id, "failed", error=detailed_error)
            queue_service.delete(EXTRACTION_QUEUE, message)
        finally:
            ingestion_service.release_processing_lock(file_id)

    # ── Stage 2: Enrichment (Chunk → Embed → Index) ─────────────

    def _handle_enrichment(self, message, payload: dict):
        """Chunk text → generate embeddings → index in Azure AI Search."""
        from src.api.modules.ingestion.chunking import chunk_text
        from src.api.modules.embeddings.service import EmbeddingsService
        from src.api.modules.ingestion.azure_storage import azure_storage_service
        from src.api.modules.ingestion.service import ingestion_service
        from src.api.modules.processing.service import ProcessingService

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
            queue_service.delete(ENRICHMENT_QUEUE, message)
            return

        if not ingestion_service.acquire_processing_lock(file_id):
            return

        try:
            # Step 1: Chunk
            chunks = chunk_text(text)

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

            # Do not mark ready if indexing silently failed; this avoids ready+doc_count=0 drift.
            if chunks and indexed == 0:
                raise RuntimeError(
                    f"Chunk indexing produced 0 indexed docs for {filename}; leaving file as failed for retry"
                )

            # Step 4: Run AI enrichment (LLM summary + CU fields + filters)
            cu_fields = payload.get("cu_fields", {})

            # Generate summary in a separate LLM stage (decoupled from CU extraction).
            summary_text = str(metadata.get("summary", "") or "").strip()
            if not summary_text:
                try:
                    processing_service = ProcessingService()
                    # Cap prompt size to avoid very large requests while preserving core context.
                    summary_input = text[:30000]
                    summary_resp = processing_service.summarize(summary_input, max_length=180, style="concise")
                    summary_text = (summary_resp.summary or "").strip()
                    if summary_text:
                        metadata["summary"] = summary_text
                except Exception as e:
                    logger.warning(f"[enrichment] LLM summary generation failed for {filename}: {e}")

            doc_data = {
                "id": file_id,
                "type": payload.get("ext", ""),
                "text": text,
                "metadata": metadata,
            }
            if summary_text:
                doc_data["summary"] = summary_text
            # Forward CU-extracted fields so _track_file can reuse them
            if cu_fields.get("key_phrases"):
                doc_data["key_phrases"] = cu_fields["key_phrases"]
            if cu_fields.get("topic"):
                doc_data["topics"] = [cu_fields["topic"]]

            ingestion_service.finalize_ingestion([doc_data], filename)

            # Mark as ready
            ingestion_service._update_file_status(file_id, "ready")

            # Delete enrichment message
            queue_service.delete(ENRICHMENT_QUEUE, message)

        except Exception as e:
            import traceback
            error_msg = f"Enrichment failed for {filename}: {str(e)}"
            tb = traceback.format_exc()
            logger.error(f"[enrichment] {error_msg}\n{tb}")
            # Provide detailed error context to user
            detailed_error = f"{error_msg} (Check logs for details)"
            ingestion_service._update_file_status(file_id, "failed", error=detailed_error)
        finally:
            ingestion_service.release_processing_lock(file_id)


queue_worker = QueueWorker()
