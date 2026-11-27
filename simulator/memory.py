"""Paging / memory management.

- translate(logical_address, page_size) -> (page_number, offset)
- PageTable: per-process page -> frame mapping with valid bits
- MemoryManager: physical frames shared by all processes, with
  allocate / access / free. Eviction is decided online by the
  configured replacement policy (FIFO / LRU / LFU / CLOCK).
  OPTIMAL needs future knowledge, so at runtime it falls back to LRU;
  the offline Optimal simulation lives in page_replacement.py.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


def translate(logical_address: int, page_size: int) -> Tuple[int, int]:
    """Split a logical address into (page_number, offset)."""
    if page_size <= 0 or (page_size & (page_size - 1)) != 0:
        raise ValueError("page_size must be a positive power of two (e.g. 1024, 4096)")
    if logical_address < 0:
        raise ValueError("logical_address must be >= 0")
    return logical_address // page_size, logical_address % page_size


def physical_address(frame_number: int, offset: int, page_size: int) -> int:
    return frame_number * page_size + offset


@dataclass
class PageTableEntry:
    frame: Optional[int] = None
    valid: bool = False
    referenced: bool = False
    modified: bool = False


@dataclass
class PageTable:
    pid: str
    num_pages: int
    entries: Dict[int, PageTableEntry] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entries = {p: PageTableEntry() for p in range(self.num_pages)}

    def map(self, page: int, frame: int) -> None:
        self.entries[page].frame = frame
        self.entries[page].valid = True
        self.entries[page].referenced = True

    def unmap(self, page: int) -> None:
        self.entries[page].frame = None
        self.entries[page].valid = False

    def lookup(self, page: int) -> Optional[int]:
        e = self.entries.get(page)
        return e.frame if e and e.valid else None

    def __str__(self) -> str:
        lines = [f"Page table for {self.pid}:"]
        lines.append(f"{'Page':<6}{'Frame':<7}{'Valid':<7}{'Ref':<5}{'Mod':<5}")
        for page, e in sorted(self.entries.items()):
            lines.append(
                f"{page:<6}{e.frame if e.frame is not None else '-':<7}"
                f"{str(e.valid):<7}{str(e.referenced):<5}{str(e.modified):<5}"
            )
        return "\n".join(lines)


@dataclass
class MemoryManager:
    """Physical memory: a fixed pool of frames shared by all processes."""

    num_frames: int
    page_size: int = 4096
    replacement: str = "lru"
    frames: List[Optional[Tuple[str, int]]] = field(init=False)
    page_tables: Dict[str, PageTable] = field(default_factory=dict)
    faults: int = 0
    hits: int = 0

    # Internal replacement state (not part of the public API)
    _time: int = field(default=0, repr=False)
    _load_order: deque = field(default_factory=deque, repr=False)  # FIFO: frame indices
    _last_used: Dict[int, int] = field(default_factory=dict, repr=False)  # LRU
    _use_count: Dict[int, int] = field(default_factory=dict, repr=False)  # LFU
    _ref_bits: List[int] = field(default_factory=list, repr=False)  # CLOCK
    _clock_hand: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        if self.num_frames <= 0:
            raise ValueError("num_frames must be > 0")
        self.frames = [None] * self.num_frames
        self._ref_bits = [0] * self.num_frames

    def create_process(self, pid: str, num_pages: int) -> PageTable:
        table = PageTable(pid, num_pages)
        self.page_tables[pid] = table
        return table

    def _choose_victim(self) -> int:
        policy = self.replacement.strip().lower()
        if policy == "fifo":
            return self._load_order[0]
        if policy == "lfu":
            return min(
                range(self.num_frames),
                key=lambda i: (self._use_count.get(i, 0), self._last_used.get(i, 0)),
            )
        if policy == "clock":
            while True:
                if self._ref_bits[self._clock_hand] == 0:
                    victim = self._clock_hand
                    self._clock_hand = (self._clock_hand + 1) % self.num_frames
                    return victim
                self._ref_bits[self._clock_hand] = 0
                self._clock_hand = (self._clock_hand + 1) % self.num_frames
        # LRU (default, and fallback for OPTIMAL at runtime)
        return min(range(self.num_frames), key=lambda i: self._last_used.get(i, 0))

    def access(self, pid: str, page: int) -> Tuple[bool, Optional[Tuple[str, int]]]:
        table = self.page_tables.get(pid)
        if table is None:
            raise ValueError(f"No page table for process {pid!r} - call create_process first")
        self._time += 1
        frame = table.lookup(page)
        if frame is not None:
            self.hits += 1
            self._last_used[frame] = self._time
            self._use_count[frame] = self._use_count.get(frame, 0) + 1
            self._ref_bits[frame] = 1
            return True, None

        # Page fault
        self.faults += 1
        evicted: Optional[Tuple[str, int]] = None
        if None in self.frames:
            idx = self.frames.index(None)
            self.frames[idx] = (pid, page)
            table.map(page, idx)
            self._load_order.append(idx)
        else:
            idx = self._choose_victim()
            evicted = self.frames[idx]
            if evicted:
                old_pid, old_page = evicted
                if old_pid in self.page_tables:
                    self.page_tables[old_pid].unmap(old_page)
                if idx in self._load_order:
                    self._load_order.remove(idx)
            self.frames[idx] = (pid, page)
            table.map(page, idx)
            self._load_order.append(idx)
        self._last_used[idx] = self._time
        self._use_count[idx] = 1
        self._ref_bits[idx] = 1
        return False, evicted

    def free_process(self, pid: str) -> None:
        table = self.page_tables.pop(pid, None)
        if table is None:
            return
        for i, slot in enumerate(self.frames):
            if slot and slot[0] == pid:
                self.frames[i] = None
                self._ref_bits[i] = 0
                self._last_used.pop(i, None)
                self._use_count.pop(i, None)
                if i in self._load_order:
                    self._load_order.remove(i)

    @property
    def free_frames(self) -> int:
        return sum(1 for f in self.frames if f is None)

    @property
    def used_frames(self) -> int:
        return self.num_frames - self.free_frames

    def status(self) -> str:
        lines = [f"Memory: {self.used_frames}/{self.num_frames} frames used, "
                 f"{self.hits} hits, {self.faults} faults"]
        for i, slot in enumerate(self.frames):
            lines.append(f"  Frame {i}: {slot[0]} page {slot[1]}" if slot else f"  Frame {i}: free")
        return "\n".join(lines)
