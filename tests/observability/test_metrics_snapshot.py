from guanchen_v2.observability.metrics import MetricsCollector


def test_metrics_snapshot():
    metrics = MetricsCollector()
    metrics.increment("test_counter", 1)
    metrics.increment("test_counter", 2)
    metrics.observe("test_latency", 10.0)
    metrics.observe("test_latency", 20.0)

    snapshot = metrics.snapshot()
    assert snapshot["counters"]["test_counter"] == 3
    assert snapshot["observations"]["test_latency"]["count"] == 2
    assert snapshot["observations"]["test_latency"]["average"] == 15.0
