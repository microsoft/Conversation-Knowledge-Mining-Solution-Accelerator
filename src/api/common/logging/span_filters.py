"""
Custom OpenTelemetry SpanProcessor filters to reduce telemetry noise in Application Insights.
"""

import logging
from opentelemetry.sdk.trace import SpanProcessor, ReadableSpan
from opentelemetry.trace import SpanContext, TraceFlags

logger = logging.getLogger(__name__)


def _unsample(span: ReadableSpan) -> None:
    """Set trace_flags to 0 so BatchSpanProcessor skips exporting this span."""
    try:
        span._context = SpanContext(
            trace_id=span.context.trace_id,
            span_id=span.context.span_id,
            is_remote=span.context.is_remote,
            trace_flags=TraceFlags(0),
            trace_state=span.context.trace_state,
        )
    except (AttributeError, TypeError) as e:
        # Gracefully handle SDK changes where _context might not be mutable
        logger.debug("Unable to unsample span %s: %s", span.name, e)


class DropASGIResponseBodySpanProcessor(SpanProcessor):
    """
    Filters out ASGI http.response.body internal dependency spans from Application Insights.

    FastAPI's StreamingResponse yields one ASGI 'http.response.body' send event per chunk.
    The OpenTelemetry ASGI instrumentation creates a child span for each of these events,
    resulting in hundreds of low-value 'POST /api/chat http send' dependency entries per
    chat request.

    Only spans with asgi.event.type == 'http.response.body' are dropped.
    Spans for 'http.response.start' (sent once per request for headers) are kept.
    """

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span: ReadableSpan) -> None:
        if (span.attributes or {}).get("asgi.event.type") == "http.response.body":
            _unsample(span)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


class DropCosmosDependencySpanProcessor(SpanProcessor):
    """
    Filters out Cosmos DB HTTP dependency spans from Application Insights.

    The azure-cosmos SDK uses azure-core, which via azure-core-tracing-opentelemetry
    creates a span for every Cosmos DB HTTP call (reads, writes, queries).
    These appear as 'POST .documents.azure.com/...' dependency entries and add
    significant noise without actionable value in Application Insights.

    Spans are identified by db.system == 'cosmosdb' (set by azure-core-tracing-opentelemetry)
    or by the presence of the Cosmos DB endpoint in the span name.
    """

    def on_start(self, span, parent_context=None):
        pass

    def on_end(self, span: ReadableSpan) -> None:
        attrs = span.attributes or {}
        span_name = span.name or ""
        if (
            attrs.get("db.system") == "cosmosdb"
            or ".documents.azure.com" in span_name
            or span_name.endswith("documents.azure.com")
        ):
            _unsample(span)

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True
