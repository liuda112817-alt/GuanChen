import threading
from collections import defaultdict, deque
from typing import Any


class MetricsCollector:
    """基础内存指标收集器，未来可对接到 Prometheus/StatsD"""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._observations = defaultdict(lambda: deque(maxlen=1000))
        self._counts = defaultdict(int)
        self._sums = defaultdict(float)
        self._lock = threading.Lock()

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._observations[name].append(value)
            self._counts[name] += 1
            self._sums[name] += value

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_average_observation(self, name: str) -> float:
        with self._lock:
            count = self._counts.get(name, 0)
            return self._sums.get(name, 0) / count if count else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            observations = {
                name: {
                    "count": self._counts[name],
                    "average": round(
                        self._sums[name] / self._counts[name] if values else 0.0,
                        2,
                    ),
                    "retained_samples": len(values),
                }
                for name, values in self._observations.items()
            }

        return {
            "counters": counters,
            "observations": observations,
        }
