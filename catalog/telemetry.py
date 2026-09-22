"""A bounded local exporter; no telemetry is sent to a third-party service."""

from collections import deque
from threading import Lock

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.sampling import ALWAYS_ON


class LocalExporter(SpanExporter):
    def __init__(self):
        self.spans = deque(maxlen=256)
        self.lock = Lock()

    def export(self, spans):
        with self.lock:
            for span in spans:
                if (
                    span.name == "demo.read"
                    and span.context is not None
                    and span.start_time is not None
                    and span.end_time is not None
                ):
                    self.spans.append(
                        {
                            "name": span.name,
                            "run": (span.attributes or {}).get("demo_run"),
                            "trace_id": format(span.context.trace_id, "032x"),
                            "duration_ms": round((span.end_time - span.start_time) / 1e6, 3),
                        }
                    )
        return SpanExportResult.SUCCESS

    def for_run(self, token):
        with self.lock:
            return [s for s in self.spans if s["run"] == token]


exporter = LocalExporter()
provider = TracerProvider(sampler=ALWAYS_ON)
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
