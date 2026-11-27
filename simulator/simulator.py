"""Combined simulator: schedule processes, then run their page
references through shared physical memory in scheduled order.

This shows the interaction the two halves have in a real OS:
scheduling decides *when* a process runs, paging decides *whether*
its pages are in memory when it does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .memory import MemoryManager
from .page_replacement import PageReplacementResult, compare_all, simulate
from .process import Process
from .scheduling import ScheduleResult, run


def demo_processes() -> List[Process]:
    """Classic textbook example used by the demo / CLI defaults."""
    return [
        Process("P1", arrival_time=0, burst_time=8, priority=2,
                page_references=[1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]),
        Process("P2", arrival_time=1, burst_time=4, priority=1,
                page_references=[3, 2, 1, 0, 3, 2, 4, 3, 2, 1, 0, 4]),
        Process("P3", arrival_time=2, burst_time=9, priority=3,
                page_references=[0, 1, 7, 0, 1, 2, 0, 1, 7, 0, 1]),
        Process("P4", arrival_time=3, burst_time=5, priority=2,
                page_references=[2, 3, 2, 1, 5, 6, 2, 1, 2, 3, 6, 3]),
    ]


CLASSIC_REFERENCE_STRING = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
# With 3 frames: FIFO 15 faults, LRU 12, Optimal 9 - the standard textbook result.


@dataclass
class CombinedResult:
    schedule: ScheduleResult
    num_frames: int
    replacement: str
    total_faults: int
    total_hits: int
    per_process_faults: Dict[str, int] = field(default_factory=dict)
    per_process_hits: Dict[str, int] = field(default_factory=dict)
    memory_log: List[str] = field(default_factory=list)

    def summary(self) -> str:
        total = self.total_faults + self.total_hits
        rate = self.total_faults / total if total else 0.0
        lines = [
            f"Scheduling: {self.schedule.algorithm}",
            f"Memory: {self.num_frames} frames, {self.replacement.upper()} replacement",
            f"Total page accesses: {total}, faults: {self.total_faults}, "
            f"hits: {self.total_hits} (fault rate {rate:.1%})",
            "",
            "Per-process page faults:",
        ]
        for pid in sorted(self.per_process_faults):
            lines.append(
                f"  {pid}: {self.per_process_faults[pid]} faults, "
                f"{self.per_process_hits.get(pid, 0)} hits"
            )
        return "\n".join(lines)


class CombinedSimulator:
    def __init__(self, num_frames: int = 3, replacement: str = "lru", page_size: int = 4096):
        self.num_frames = num_frames
        self.replacement = replacement
        self.page_size = page_size

    def run(self, processes: List[Process], algorithm: str = "fcfs",
            quantum: int = 2, preemptive_priority: bool = False) -> CombinedResult:
        schedule = run(processes, algorithm, quantum=quantum,
                       preemptive_priority=preemptive_priority)

        memory = MemoryManager(self.num_frames, page_size=self.page_size,
                               replacement=self.replacement)
        per_faults: Dict[str, int] = {p.pid: 0 for p in processes}
        per_hits: Dict[str, int] = {p.pid: 0 for p in processes}
        log: List[str] = []

        # Create a page table per process. Size = max referenced page + 1.
        for p in processes:
            n_pages = (max(p.page_references) + 1) if p.page_references else 1
            memory.create_process(p.pid, n_pages)

        # Run page references in Gantt order (the order processes actually ran).
        # For non-preemptive algorithms this is completion order; for RR/SRTF
        # it follows the time slices, which is the realistic interleaving.
        seen: Dict[str, int] = {p.pid: 0 for p in processes}
        for segment in schedule.gantt:
            if segment.pid == "IDLE":
                continue
            pid = segment.pid
            proc = next(p for p in processes if p.pid == pid)
            # One page reference per unit of CPU time in this segment,
            # cycling through the process's reference string.
            for _ in range(segment.end - segment.start):
                if not proc.page_references:
                    break
                idx = seen[pid] % len(proc.page_references)
                page = proc.page_references[idx]
                seen[pid] += 1
                hit, evicted = memory.access(pid, page)
                if hit:
                    per_hits[pid] += 1
                else:
                    per_faults[pid] += 1
                    evict_note = f", evicted {evicted[0]} page {evicted[1]}" if evicted else ""
                    log.append(f"t={segment.start}: {pid} page {page} -> FAULT{evict_note}")
            # Free frames when a process finishes, like a real OS would
            # on exit - only if this was its last segment.
            if any(p.pid == pid and p.completion_time == segment.end for p in schedule.processes):
                # Keep the frames for the summary in this demo run; freeing
                # here would hide the final state, so we log it instead.
                pass

        return CombinedResult(
            schedule=schedule,
            num_frames=self.num_frames,
            replacement=self.replacement,
            total_faults=memory.faults,
            total_hits=memory.hits,
            per_process_faults=per_faults,
            per_process_hits=per_hits,
            memory_log=log,
        )


def compare_scheduling(processes: List[Process], quantum: int = 2) -> List[ScheduleResult]:
    """Run every scheduling algorithm on the same processes."""
    return [
        run(processes, "fcfs"),
        run(processes, "sjf"),
        run(processes, "srtf"),
        run(processes, "rr", quantum=quantum),
        run(processes, "priority"),
        run(processes, "priority", preemptive_priority=True),
    ]


def compare_replacement(reference_string: List[int], num_frames: int) -> List[PageReplacementResult]:
    return compare_all(reference_string, num_frames)
