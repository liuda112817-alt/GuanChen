from collections import defaultdict
import threading
from typing import Any


class MetricsCollector:
    """基础内存指标收集器，未来可对接到 Prometheus/StatsD"""

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._observations: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def increment(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            self._observations[name].append(value)

    def get_counter(self, name: str) -> int:
        return self._counters.get(name, 0)

    def get_average_observation(self, name: str) -> float:
        obs = self._observations.get(name, [])
        return sum(obs) / len(obs) if obs else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            counters = dict(self._counters)
            observations = {
                name: {
                    "count": len(values),
                    "average": round(
                        sum(values) / len(values) if values else 0.0,
                        2,
                    ),
                }
                for name, values in self._observations.items()
            }

        return {
            "counters": counters,
            "observations": observations,
        }
