"""Process model used by both the scheduler and the memory simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Process:
    pid: str
    arrival_time: int = 0
    burst_time: int = 0
    priority: int = 1  # lower number = higher priority
    page_references: List[int] = field(default_factory=list)

    # Filled in by the scheduler - do not set these by hand
    remaining_time: int = field(init=False)
    start_time: Optional[int] = None
    completion_time: Optional[int] = None
    waiting_time: int = 0
    turnaround_time: int = 0
    response_time: Optional[int] = None

    def __post_init__(self) -> None:
        if self.burst_time < 0:
            raise ValueError("burst_time must be >= 0")
        if self.arrival_time < 0:
            raise ValueError("arrival_time must be >= 0")
        self.remaining_time = self.burst_time

    def reset(self) -> None:
        """Reset scheduler-computed fields so a Process can be re-run."""
        self.remaining_time = self.burst_time
        self.start_time = None
        self.completion_time = None
        self.waiting_time = 0
        self.turnaround_time = 0
        self.response_time = None

    def copy(self) -> "Process":
        return Process(
            pid=self.pid,
            arrival_time=self.arrival_time,
            burst_time=self.burst_time,
            priority=self.priority,
            page_references=list(self.page_references),
        )


@dataclass
class GanttSegment:
    pid: str  # "IDLE" for idle CPU time
    start: int
    end: int

    def __str__(self) -> str:
        return f"{self.pid}[{self.start}-{self.end}]"


@dataclass
class ScheduleResult:
    algorithm: str
    gantt: List[GanttSegment]
    processes: List[Process]
    total_time: int

    @property
    def avg_waiting_time(self) -> float:
        if not self.processes:
            return 0.0
        return sum(p.waiting_time for p in self.processes) / len(self.processes)

    @property
    def avg_turnaround_time(self) -> float:
        if not self.processes:
            return 0.0
        return sum(p.turnaround_time for p in self.processes) / len(self.processes)

    @property
    def avg_response_time(self) -> float:
        vals = [p.response_time for p in self.processes if p.response_time is not None]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def throughput(self) -> float:
        return len(self.processes) / self.total_time if self.total_time else 0.0

    @property
    def cpu_utilization(self) -> float:
        busy = sum(s.end - s.start for s in self.gantt if s.pid != "IDLE")
        return (busy / self.total_time * 100) if self.total_time else 0.0

    def table(self) -> str:
        lines = [
            f"{'PID':<6}{'Arrival':<9}{'Burst':<7}{'Priority':<9}"
            f"{'Start':<7}{'Finish':<8}{'Waiting':<9}{'Turnaround':<11}{'Response':<9}",
            "-" * 74,
        ]
        for p in sorted(self.processes, key=lambda x: x.pid):
            lines.append(
                f"{p.pid:<6}{p.arrival_time:<9}{p.burst_time:<7}{p.priority:<9}"
                f"{p.start_time if p.start_time is not None else '-':<7}"
                f"{p.completion_time if p.completion_time is not None else '-':<8}"
                f"{p.waiting_time:<9}{p.turnaround_time:<11}"
                f"{p.response_time if p.response_time is not None else '-':<9}"
            )
        lines.append("-" * 74)
        lines.append(f"Average waiting time:    {self.avg_waiting_time:.2f}")
        lines.append(f"Average turnaround time: {self.avg_turnaround_time:.2f}")
        lines.append(f"Average response time:   {self.avg_response_time:.2f}")
        lines.append(f"Throughput:              {self.throughput:.3f} processes / time unit")
        lines.append(f"CPU utilization:         {self.cpu_utilization:.1f}%")
        return "\n".join(lines)

    def gantt_chart(self) -> str:
        if not self.gantt:
            return "(empty)"
        bar = " | ".join(str(s) for s in self.gantt)
        # Simple text timeline
        timeline = ""
        for s in self.gantt:
            width = max(1, s.end - s.start)
            timeline += f"| {'-' * width} {s.pid} "
        return f"Gantt: {bar}\n{timeline}|"
