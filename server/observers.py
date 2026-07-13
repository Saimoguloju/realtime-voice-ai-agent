#
# Pipeline observer that persists per-service latency metrics.
#

"""Latency observer for the voice agent.

Watches ``MetricsFrame``s flowing through the pipeline and records each
service's TTFB (time to first byte) and processing time into SQLite. These
are the numbers behind the dashboard's p50/p95 latency table — the metric
that matters most in real-time voice: perceived responsiveness.
"""

from loguru import logger
from pipecat.frames.frames import MetricsFrame
from pipecat.metrics.metrics import ProcessingMetricsData, TTFBMetricsData
from pipecat.observers.base_observer import BaseObserver, FramePushed

import storage


class LatencyMetricsObserver(BaseObserver):
    """Records TTFB and processing-time metrics for every service in the pipeline."""

    def __init__(self, session_id: str):
        super().__init__()
        self._session_id = session_id
        # A MetricsFrame is observed once per processor hop; dedupe by frame id.
        self._seen_frame_ids: set[int] = set()

    async def on_push_frame(self, data: FramePushed):
        frame = data.frame
        if not isinstance(frame, MetricsFrame) or frame.id in self._seen_frame_ids:
            return
        self._seen_frame_ids.add(frame.id)

        for item in frame.data:
            if isinstance(item, TTFBMetricsData):
                metric_type, value = "ttfb", item.value
            elif isinstance(item, ProcessingMetricsData):
                metric_type, value = "processing", item.value
            else:
                continue
            if value <= 0:
                continue
            try:
                storage.record_metric(self._session_id, item.processor, metric_type, value)
            except Exception as e:
                logger.warning(f"Failed to record metric: {e}")
