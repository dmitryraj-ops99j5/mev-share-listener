import time
from collections import deque
from dataclasses import dataclass


@dataclass
class StatsSnapshot:
    total_received: int
    total_matched: int
    total_dropped: int
    rate_1s: float
    rate_60s: float


class StreamStats:
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.total_received = 0
        self.total_matched = 0
        self.total_dropped = 0
        self._events_ts = deque()

    def record_event(self, matched: bool = False, dropped: bool = False):
        now = time.monotonic()
        self.total_received += 1
        if matched:
            self.total_matched += 1
        if dropped:
            self.total_dropped += 1

        self._events_ts.append(now)
        self._prune(now)

    def _prune(self, now: float):
        cutoff = now - self.window_size
        while self._events_ts and self._events_ts[0] < cutoff:
            self._events_ts.popleft()

    def snapshot(self) -> StatsSnapshot:
        now = time.monotonic()
        self._prune(now)
        
        # Walk backwards since timestamps are monotonically ordered
        one_sec_cutoff = now - 1.0
        recent_1s = 0
        for ts in reversed(self._events_ts):
            if ts < one_sec_cutoff:
                break
            recent_1s += 1

        rate_60s = len(self._events_ts) / float(self.window_size) if self.window_size > 0 else 0.0

        return StatsSnapshot(
            total_received=self.total_received,
            total_matched=self.total_matched,
            total_dropped=self.total_dropped,
            rate_1s=float(recent_1s),
            rate_60s=round(rate_60s, 2),
        )
