"""Restore Azure AI Search ``get_url`` enrichment on streaming citations.

Pre-GA ``agent-framework-azure-ai==1.0.0rc2`` enriched ``url_citation``
streaming annotations with a per-document REST URL exposed under
``additional_properties.get_url``. That subclass was removed when the
``azure-ai`` package was retired at GA.

In the GA ``agent_framework_openai._chat_client._parse_chunk_from_openai``:

1. ``response.azure_ai_search_call_output.done`` events fall through to
   the default ``case _:`` debug log, so the ``output.get_urls[]`` array
   carrying per-document REST URLs is silently dropped.
2. ``url_citation`` annotations (added by upstream PR #5071) emit only
   ``title`` and ``url`` (the search-service root URL).

This patch wraps that method to:

1. Cache ``get_urls`` per-stream when seeing the search-call-output event.
2. Inject ``additional_properties.get_url`` on ``url_citation`` annotations
   using ``annotation_index`` as the lookup key, matching the pre-GA
   contract that the citation extraction in ``chat_service.py`` reads.

Tracking upstream: https://github.com/microsoft/agent-framework/issues/5995
Safe to remove once upstream ports the ``get_url`` enrichment into
``agent_framework_openai`` or ``agent_framework_foundry``.
"""

from __future__ import annotations

import logging
import re
from typing import Any

_DOC_INDEX_RE = re.compile(r"^doc_(\d+)$")

logger = logging.getLogger(__name__)

_PATCH_MARKER = "_kmsa_search_citations_patched"
_CACHE_ATTR = "_kmsa_search_get_urls_cache"
_TARGET_METHOD = "_parse_chunk_from_openai"
_TARGET_CLASS = "RawOpenAIChatClient"
_UPSTREAM_ISSUE = "https://github.com/microsoft/agent-framework/issues/5995"


def apply() -> None:
    """Idempotently patch RawOpenAIChatClient._parse_chunk_from_openai.

    Safe to call multiple times; the second call is a no-op.
    Logs a warning (does not raise) if upstream has renamed the target,
    so app startup still succeeds with degraded citations.
    """
    try:
        from agent_framework_openai import _chat_client as _cc
    except ImportError:
        logger.warning(
            "agent_framework_openai not installed; "
            "Azure AI Search citation patch skipped"
        )
        return

    target_cls = getattr(_cc, _TARGET_CLASS, None)
    if target_cls is None or not hasattr(target_cls, _TARGET_METHOD):
        logger.warning(
            "agent-framework upgrade broke citation patch: %s.%s no longer exists. "
            "Per-document URLs (get_url) will be missing on Azure AI Search "
            "citations. See %s",
            _TARGET_CLASS, _TARGET_METHOD, _UPSTREAM_ISSUE,
        )
        return

    # Idempotency guard: the marker travels with the patched class, so a
    # second call (or a re-import) is a no-op even across module reloads.
    if getattr(target_cls, _PATCH_MARKER, False):
        return

    _original = getattr(target_cls, _TARGET_METHOD)

    def _patched(self: Any, event: Any, *args: Any, **kwargs: Any) -> Any:
        event_type = getattr(event, "type", None)

        # Reset per-stream cache so back-to-back requests on the same client
        # instance don't cross-pollute citation enrichment.
        if event_type in ("response.created", "response.in_progress"):
            setattr(self, _CACHE_ATTR, [])

        # Capture get_urls from azure_ai_search_call_output items on .done.
        # The .added event for this item has output='[]'; the .done event
        # carries the actual documents + get_urls.
        if event_type == "response.output_item.done":
            try:
                done_item = getattr(event, "item", None)
                if getattr(done_item, "type", None) == "azure_ai_search_call_output":
                    output = getattr(done_item, "output", None)
                    get_urls = getattr(output, "get_urls", None)
                    if get_urls is None and isinstance(output, dict):
                        get_urls = output.get("get_urls")
                    if get_urls is None and isinstance(output, str):
                        # Some SDK versions deliver `output` as a JSON string.
                        import json as _json
                        try:
                            parsed = _json.loads(output)
                            if isinstance(parsed, dict):
                                get_urls = parsed.get("get_urls")
                        except Exception:  # noqa: BLE001
                            pass
                    if get_urls:
                        cache = getattr(self, _CACHE_ATTR, None)
                        if cache is None:
                            cache = []
                            setattr(self, _CACHE_ATTR, cache)
                        cache.extend(get_urls)
            except Exception:  # noqa: BLE001 - defensive: never break streaming
                logger.debug(
                    "search-citation patch: failed to capture get_urls",
                    exc_info=True,
                )

        result = _original(self, event, *args, **kwargs)

        # Enrich url_citation annotations emitted by the base method's
        # response.output_text.annotation.added branch.
        if event_type == "response.output_text.annotation.added":
            try:
                cache = getattr(self, _CACHE_ATTR, None) or []
                if cache:
                    for content in (getattr(result, "contents", None) or []):
                        for ann in (getattr(content, "annotations", None) or []):
                            if not isinstance(ann, dict):
                                continue
                            if ann.get("type") != "citation":
                                continue
                            add_props = ann.get("additional_properties") or {}
                            # Idempotent: do not overwrite if upstream ever ships
                            # the fix and starts populating get_url itself.
                            if add_props.get("get_url"):
                                continue
                            # Map by title "doc_<N>" where N is the index into
                            # the search results (and thus into get_urls). The
                            # model can cite the same doc multiple times, so
                            # annotation_index (a running counter) is unreliable.
                            title = ann.get("title") or ""
                            m = _DOC_INDEX_RE.match(str(title))
                            doc_idx = int(m.group(1)) if m else None
                            if doc_idx is None:
                                doc_idx = add_props.get("annotation_index")
                            if isinstance(doc_idx, int) and 0 <= doc_idx < len(cache):
                                add_props["get_url"] = cache[doc_idx]
                                ann["additional_properties"] = add_props
            except Exception:  # noqa: BLE001
                logger.debug(
                    "search-citation patch: failed to enrich annotation",
                    exc_info=True,
                )

        # Release per-stream state once the response completes.
        if event_type == "response.completed":
            try:
                if hasattr(self, _CACHE_ATTR):
                    delattr(self, _CACHE_ATTR)
            except Exception:  # noqa: BLE001
                pass

        return result

    setattr(target_cls, _TARGET_METHOD, _patched)
    setattr(target_cls, _PATCH_MARKER, True)  # marks patch as applied (checked in apply() guard)
    logger.info(
        "Applied Azure AI Search citation patch on %s.%s (workaround for %s)",
        _TARGET_CLASS, _TARGET_METHOD, _UPSTREAM_ISSUE,
    )


# Apply on import so a single
# `import services._patches.agent_framework_search_citations`
# from chat_service.py is enough.
apply()
