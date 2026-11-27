"""Process Scheduling + Memory Management Simulator."""

from .memory import MemoryManager, PageTable, physical_address, translate
from .page_replacement import compare_all, simulate
from .process import GanttSegment, Process, ScheduleResult
from .scheduling import ALGORITHMS, fcfs, priority, round_robin, run, sjf, srtf
from .simulator import CombinedResult, CombinedSimulator, demo_processes

__all__ = [
    "Process", "ScheduleResult", "GanttSegment",
    "fcfs", "sjf", "srtf", "round_robin", "priority", "run", "ALGORITHMS",
    "simulate", "compare_all",
    "MemoryManager", "PageTable", "translate", "physical_address",
    "CombinedSimulator", "CombinedResult", "demo_processes",
]

__version__ = "1.0.0"
