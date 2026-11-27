"""CPU scheduling algorithms.

All functions take a list of Process objects, copy them (so the caller's
objects are not mutated), run the algorithm, and return a ScheduleResult.

Algorithms:
  FCFS      - First Come First Served (non-preemptive)
  SJF       - Shortest Job First (non-preemptive)
  SRTF      - Shortest Remaining Time First (preemptive SJF)
  RR        - Round Robin (preemptive, needs a time quantum)
  PRIORITY  - Priority, non-preemptive by default, preemptive with flag
"""

from __future__ import annotations

from collections import deque
from typing import List, Optional

from .process import GanttSegment, Process, ScheduleResult


def _finish(processes: List[Process], algorithm: str, gantt: List[GanttSegment]) -> ScheduleResult:
    total = max((p.completion_time or 0) for p in processes) if processes else 0
    # Merge adjacent segments for the same PID for a cleaner Gantt chart
    merged: List[GanttSegment] = []
    for seg in gantt:
        if merged and merged[-1].pid == seg.pid and merged[-1].end == seg.start:
            merged[-1].end = seg.end
        else:
            merged.append(GanttSegment(seg.pid, seg.start, seg.end))
    for p in processes:
        if p.completion_time is not None:
            p.turnaround_time = p.completion_time - p.arrival_time
            p.waiting_time = p.turnaround_time - p.burst_time
    return ScheduleResult(algorithm=algorithm, gantt=merged, processes=processes, total_time=total)


def _add_segment(gantt: List[GanttSegment], pid: str, start: int, end: int) -> None:
    if end > start:
        gantt.append(GanttSegment(pid, start, end))


def fcfs(processes: List[Process]) -> ScheduleResult:
    procs = sorted((p.copy() for p in processes), key=lambda p: (p.arrival_time, p.pid))
    gantt: List[GanttSegment] = []
    time = 0
    for p in procs:
        if time < p.arrival_time:
            _add_segment(gantt, "IDLE", time, p.arrival_time)
            time = p.arrival_time
        p.start_time = time
        p.response_time = time - p.arrival_time
        time += p.burst_time
        p.completion_time = time
        _add_segment(gantt, p.pid, p.start_time, time)
    return _finish(procs, "FCFS", gantt)


def sjf(processes: List[Process]) -> ScheduleResult:
    """Shortest Job First, non-preemptive."""
    procs = [p.copy() for p in processes]
    gantt: List[GanttSegment] = []
    time = 0
    done = 0
    remaining = list(procs)
    while done < len(procs):
        ready = [p for p in remaining if p.arrival_time <= time]
        if not ready:
            nxt = min(p.arrival_time for p in remaining)
            _add_segment(gantt, "IDLE", time, nxt)
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.burst_time, x.arrival_time, x.pid))
        remaining.remove(p)
        p.start_time = time
        p.response_time = time - p.arrival_time
        time += p.burst_time
        p.completion_time = time
        _add_segment(gantt, p.pid, p.start_time, time)
        done += 1
    return _finish(procs, "SJF (non-preemptive)", gantt)


def srtf(processes: List[Process]) -> ScheduleResult:
    """Shortest Remaining Time First, preemptive SJF. Tick-by-tick."""
    procs = [p.copy() for p in processes]
    gantt: List[GanttSegment] = []
    time = 0
    done = 0
    while done < len(procs):
        ready = [p for p in procs if p.arrival_time <= time and p.remaining_time > 0]
        if not ready:
            nxt = min(p.arrival_time for p in procs if p.remaining_time > 0)
            _add_segment(gantt, "IDLE", time, nxt)
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.remaining_time, x.arrival_time, x.pid))
        if p.start_time is None:
            p.start_time = time
            p.response_time = time - p.arrival_time
        _add_segment(gantt, p.pid, time, time + 1)
        p.remaining_time -= 1
        time += 1
        if p.remaining_time == 0:
            p.completion_time = time
            done += 1
    return _finish(procs, "SRTF (preemptive SJF)", gantt)


def round_robin(processes: List[Process], quantum: int = 2) -> ScheduleResult:
    if quantum <= 0:
        raise ValueError("quantum must be > 0")
    procs = sorted((p.copy() for p in processes), key=lambda p: (p.arrival_time, p.pid))
    gantt: List[GanttSegment] = []
    time = 0
    queue: deque[Process] = deque()
    idx = 0
    done = 0
    # Seed the queue
    while idx < len(procs) and procs[idx].arrival_time <= time:
        queue.append(procs[idx])
        idx += 1
    while done < len(procs):
        if not queue:
            nxt = procs[idx].arrival_time
            _add_segment(gantt, "IDLE", time, nxt)
            time = nxt
            while idx < len(procs) and procs[idx].arrival_time <= time:
                queue.append(procs[idx])
                idx += 1
            continue
        p = queue.popleft()
        if p.start_time is None:
            p.start_time = time
            p.response_time = time - p.arrival_time
        run = min(quantum, p.remaining_time)
        _add_segment(gantt, p.pid, time, time + run)
        p.remaining_time -= run
        time += run
        # Enqueue newly arrived processes first (they arrived during this slice)
        while idx < len(procs) and procs[idx].arrival_time <= time:
            queue.append(procs[idx])
            idx += 1
        if p.remaining_time > 0:
            queue.append(p)
        else:
            p.completion_time = time
            done += 1
    return _finish(procs, f"Round Robin (quantum={quantum})", gantt)


def priority(processes: List[Process], preemptive: bool = False) -> ScheduleResult:
    """Priority scheduling. Lower priority number = higher priority."""
    procs = [p.copy() for p in processes]
    gantt: List[GanttSegment] = []
    time = 0
    done = 0
    if not preemptive:
        remaining = list(procs)
        while done < len(procs):
            ready = [p for p in remaining if p.arrival_time <= time]
            if not ready:
                nxt = min(p.arrival_time for p in remaining)
                _add_segment(gantt, "IDLE", time, nxt)
                time = nxt
                continue
            p = min(ready, key=lambda x: (x.priority, x.arrival_time, x.pid))
            remaining.remove(p)
            p.start_time = time
            p.response_time = time - p.arrival_time
            time += p.burst_time
            p.completion_time = time
            _add_segment(gantt, p.pid, p.start_time, time)
            done += 1
        return _finish(procs, "Priority (non-preemptive)", gantt)

    # Preemptive, tick-by-tick
    while done < len(procs):
        ready = [p for p in procs if p.arrival_time <= time and p.remaining_time > 0]
        if not ready:
            nxt = min(p.arrival_time for p in procs if p.remaining_time > 0)
            _add_segment(gantt, "IDLE", time, nxt)
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.priority, x.arrival_time, x.pid))
        if p.start_time is None:
            p.start_time = time
            p.response_time = time - p.arrival_time
        _add_segment(gantt, p.pid, time, time + 1)
        p.remaining_time -= 1
        time += 1
        if p.remaining_time == 0:
            p.completion_time = time
            done += 1
    return _finish(procs, "Priority (preemptive)", gantt)


ALGORITHMS = {
    "fcfs": fcfs,
    "sjf": sjf,
    "srtf": srtf,
    "rr": round_robin,
    "priority": priority,
}


def run(processes: List[Process], algorithm: str, quantum: int = 2,
        preemptive_priority: bool = False) -> ScheduleResult:
    key = algorithm.strip().lower()
    if key == "rr":
        return round_robin(processes, quantum=quantum)
    if key == "priority":
        return priority(processes, preemptive=preemptive_priority)
    if key in ALGORITHMS:
        return ALGORITHMS[key](processes)
    raise ValueError(f"Unknown scheduling algorithm: {algorithm!r}. "
                     f"Choose from: {', '.join(sorted(ALGORITHMS))}")
