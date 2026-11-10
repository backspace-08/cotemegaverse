"""CFR / server diagnostics.

Records per-move latency and process CPU/peak-RSS so we can estimate how much
the solver stresses the server and how many concurrent games fit.

Aggregates live in memory (surfaced by `/cfr_stats`) and each move is appended
to `cfr_metrics.log`.
"""

import logging
import os
import resource
import time
from collections import deque
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler

LOG_FILE = "cfr_metrics.log"

_logger = logging.getLogger("cfr_metrics")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _handler = RotatingFileHandler(LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    _logger.addHandler(_handler)
    _logger.propagate = False

_WINDOW = 500


def rss_mb() -> float:
    """Peak resident set size of the process, MB (Linux: ru_maxrss is KB)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def current_rss_mb() -> float:
    """Current resident set size, MB (Linux /proc/self/statm)."""
    try:
        with open("/proc/self/statm", "r") as fh:
            pages = int(fh.read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE") / (1024.0 * 1024.0)
    except Exception:  # noqa: BLE001 - non-Linux fallback
        return rss_mb()


def cpu_seconds() -> float:
    times = os.times()
    return times.user + times.system


def cores() -> int:
    return os.cpu_count() or 1


@dataclass
class MoveMetric:
    turn: int
    latency_ms: float
    cpu_ms: float
    rss_mb: float
    value: float
    depth: int
    iters: int
    attacks: int = 0
    defends: int = 0
    bonuses: int = 0
    switch_to: int = -1


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1))))
    return ordered[index]


class CfrStats:
    def __init__(self) -> None:
        self.count = 0
        self.total_ms = 0.0
        self.total_cpu_ms = 0.0
        self.max_ms = 0.0
        self.latencies: deque[float] = deque(maxlen=_WINDOW)
        self.cpus: deque[float] = deque(maxlen=_WINDOW)
        self.last: MoveMetric | None = None

    def record(self, metric: MoveMetric) -> None:
        self.count += 1
        self.total_ms += metric.latency_ms
        self.total_cpu_ms += metric.cpu_ms
        self.max_ms = max(self.max_ms, metric.latency_ms)
        self.latencies.append(metric.latency_ms)
        self.cpus.append(metric.cpu_ms)
        self.last = metric
        switch = f" sw={metric.switch_to}" if metric.switch_to >= 0 else ""
        _logger.info(
            "turn=%d move=a%d/d%d/b%d%s value=%.4f latency=%.0fms cpu=%.0fms rss=%.0fMB",
            metric.turn, metric.attacks, metric.defends, metric.bonuses, switch,
            metric.value, metric.latency_ms, metric.cpu_ms, metric.rss_mb,
        )

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.count if self.count else 0.0

    @property
    def avg_cpu_ms(self) -> float:
        return self.total_cpu_ms / self.count if self.count else 0.0

    def report(self, active_matches: int = 0, turn_seconds: float = 20.0) -> str:
        n_cores = cores()
        if self.count == 0 or (self.avg_cpu_ms <= 0 and self.avg_ms <= 0):
            capacity = "• пока нет ходов бота - сыграй бой для оценки\n"
        else:
            cpu_ms = self.avg_cpu_ms or self.avg_ms
            # A solve occupies one core for `cpu_ms`; one PvE game spends one
            # solve per human turn (turn_seconds). CPU-saturated ceiling.
            moves_per_sec_per_core = 1000.0 / cpu_ms
            saturated = moves_per_sec_per_core * n_cores * turn_seconds
            capacity = (
                f"• потолок CPU: ~{saturated:.0f} игр\n"
                f"• с запасом ×2: ~{saturated / 2.0:.0f} игр\n"
            )
        return (
            "🤖 <b>CFR - нагрузка</b>\n"
            f"Ядер: {n_cores}\n"
            f"Ходов бота всего: {self.count}\n"
            f"Время на ход: avg {self.avg_ms:.0f}мс | p95 {_percentile(list(self.latencies), 95):.0f}мс | max {self.max_ms:.0f}мс\n"
            f"CPU на ход: avg {self.avg_cpu_ms:.0f}мс (≈{self.avg_cpu_ms / (self.avg_ms or 1) * 100:.0f}% от времени)\n"
            f"RSS (пик): {rss_mb():.0f}МБ | активных PvE: {active_matches}\n"
            "<b>Оценка ёмкости</b> (1 ход бота на игрока каждые "
            f"{turn_seconds:.0f}с):\n"
            f"{capacity}"
            "<i>Учти GIL: если Rust не отпускает GIL, реальный потолок ≈ 1 ядро.</i>"
        )


stats = CfrStats()


def measure_start() -> tuple[float, float]:
    return time.perf_counter(), cpu_seconds()


def measure_end(start: tuple[float, float]) -> tuple[float, float]:
    t0, c0 = start
    return (time.perf_counter() - t0) * 1000.0, (cpu_seconds() - c0) * 1000.0
