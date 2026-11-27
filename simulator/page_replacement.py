"""Page replacement algorithms.

simulate(reference_string, num_frames, algorithm) returns a
PageReplacementResult with faults, hits, hit ratio and a step-by-step
trace showing the frame contents after every reference.

Algorithms: FIFO, LRU, OPTIMAL, LFU, CLOCK (second chance)
"""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ReplacementStep:
    page: int
    fault: bool
    frames: List[int]  # snapshot after this reference (-1 = empty, shown as -)
    evicted: int | None = None


@dataclass
class PageReplacementResult:
    algorithm: str
    num_frames: int
    reference_string: List[int]
    steps: List[ReplacementStep] = field(default_factory=list)

    @property
    def faults(self) -> int:
        return sum(1 for s in self.steps if s.fault)

    @property
    def hits(self) -> int:
        return len(self.steps) - self.faults

    @property
    def hit_ratio(self) -> float:
        return self.hits / len(self.steps) if self.steps else 0.0

    @property
    def fault_ratio(self) -> float:
        return self.faults / len(self.steps) if self.steps else 0.0

    def summary(self) -> str:
        return (
            f"{self.algorithm}: {self.faults} page faults, {self.hits} hits "
            f"out of {len(self.steps)} references "
            f"(fault rate {self.fault_ratio:.1%}, hit rate {self.hit_ratio:.1%})"
        )

    def trace_table(self) -> str:
        lines = [f"{'Ref':<5}{'Fault':<7}{'Frames':<30}{'Evicted':<8}",
                 "-" * 50]
        for s in self.steps:
            frames = "[" + ", ".join(str(f) if f != -1 else "-" for f in s.frames) + "]"
            lines.append(
                f"{s.page:<5}{'YES' if s.fault else 'no':<7}{frames:<30}"
                f"{s.evicted if s.evicted is not None else '-':<8}"
            )
        lines.append("-" * 50)
        lines.append(self.summary())
        return "\n".join(lines)


def _empty_frames(n: int) -> List[int]:
    return [-1] * n


def fifo(reference_string: List[int], num_frames: int) -> PageReplacementResult:
    frames = _empty_frames(num_frames)
    order: deque[int] = deque()  # frame indices in load order
    steps: List[ReplacementStep] = []
    for page in reference_string:
        if page in frames:
            steps.append(ReplacementStep(page, False, list(frames)))
            continue
        evicted = None
        if -1 in frames:
            idx = frames.index(-1)
            frames[idx] = page
            order.append(idx)
        else:
            idx = order.popleft()
            evicted = frames[idx]
            frames[idx] = page
            order.append(idx)
        steps.append(ReplacementStep(page, True, list(frames), evicted))
    return PageReplacementResult("FIFO", num_frames, list(reference_string), steps)


def lru(reference_string: List[int], num_frames: int) -> PageReplacementResult:
    # OrderedDict: page -> frame index, ordered least -> most recently used
    cache: OrderedDict[int, int] = OrderedDict()
    frames = _empty_frames(num_frames)
    steps: List[ReplacementStep] = []
    for page in reference_string:
        if page in cache:
            cache.move_to_end(page)
            steps.append(ReplacementStep(page, False, list(frames)))
            continue
        evicted = None
        if len(cache) < num_frames:
            idx = frames.index(-1)
        else:
            old_page, idx = cache.popitem(last=False)
            evicted = old_page
        frames[idx] = page
        cache[page] = idx
        steps.append(ReplacementStep(page, True, list(frames), evicted))
    return PageReplacementResult("LRU", num_frames, list(reference_string), steps)


def optimal(reference_string: List[int], num_frames: int) -> PageReplacementResult:
    frames = _empty_frames(num_frames)
    steps: List[ReplacementStep] = []
    for i, page in enumerate(reference_string):
        if page in frames:
            steps.append(ReplacementStep(page, False, list(frames)))
            continue
        evicted = None
        if -1 in frames:
            idx = frames.index(-1)
        else:
            # Evict the page whose next use is farthest away (or never)
            farthest_idx, farthest_dist = 0, -1
            for j, f in enumerate(frames):
                try:
                    dist = reference_string.index(f, i + 1) - i
                except ValueError:
                    dist = float("inf")
                if dist > farthest_dist:
                    farthest_dist, farthest_idx = dist, j
            idx = farthest_idx
            evicted = frames[idx]
        frames[idx] = page
        steps.append(ReplacementStep(page, True, list(frames), evicted))
    return PageReplacementResult("OPTIMAL", num_frames, list(reference_string), steps)


def lfu(reference_string: List[int], num_frames: int) -> PageReplacementResult:
    frames = _empty_frames(num_frames)
    counts: Dict[int, int] = {}
    last_used: Dict[int, int] = {}
    steps: List[ReplacementStep] = []
    for t, page in enumerate(reference_string):
        counts[page] = counts.get(page, 0) + 1
        last_used[page] = t
        if page in frames:
            steps.append(ReplacementStep(page, False, list(frames)))
            continue
        evicted = None
        if -1 in frames:
            idx = frames.index(-1)
        else:
            # Least frequently used; tie-break by least recently used
            victim = min(frames, key=lambda f: (counts.get(f, 0), last_used.get(f, 0)))
            idx = frames.index(victim)
            evicted = victim
        frames[idx] = page
        steps.append(ReplacementStep(page, True, list(frames), evicted))
    return PageReplacementResult("LFU", num_frames, list(reference_string), steps)


def clock(reference_string: List[int], num_frames: int) -> PageReplacementResult:
    """Clock / second-chance algorithm."""
    frames = _empty_frames(num_frames)
    ref_bits = [0] * num_frames
    hand = 0
    steps: List[ReplacementStep] = []
    for page in reference_string:
        if page in frames:
            ref_bits[frames.index(page)] = 1
            steps.append(ReplacementStep(page, False, list(frames)))
            continue
        evicted = None
        if -1 in frames:
            idx = frames.index(-1)
            frames[idx] = page
            ref_bits[idx] = 1
            hand = (idx + 1) % num_frames
        else:
            while True:
                if ref_bits[hand] == 0:
                    evicted = frames[hand]
                    frames[hand] = page
                    ref_bits[hand] = 1
                    hand = (hand + 1) % num_frames
                    break
                ref_bits[hand] = 0
                hand = (hand + 1) % num_frames
            idx = None
        steps.append(ReplacementStep(page, True, list(frames), evicted))
    return PageReplacementResult("CLOCK", num_frames, list(reference_string), steps)


REPLACEMENT_ALGORITHMS = {
    "fifo": fifo,
    "lru": lru,
    "optimal": optimal,
    "opt": optimal,
    "lfu": lfu,
    "clock": clock,
}


def simulate(reference_string: List[int], num_frames: int, algorithm: str) -> PageReplacementResult:
    if num_frames <= 0:
        raise ValueError("num_frames must be > 0")
    key = algorithm.strip().lower()
    if key not in REPLACEMENT_ALGORITHMS:
        raise ValueError(f"Unknown page replacement algorithm: {algorithm!r}. "
                         f"Choose from: {', '.join(sorted(set(REPLACEMENT_ALGORITHMS)))}")
    return REPLACEMENT_ALGORITHMS[key](list(reference_string), num_frames)


def compare_all(reference_string: List[int], num_frames: int) -> List[PageReplacementResult]:
    """Run every algorithm on the same reference string - useful for comparison."""
    return [
        fifo(list(reference_string), num_frames),
        lru(list(reference_string), num_frames),
        optimal(list(reference_string), num_frames),
        lfu(list(reference_string), num_frames),
        clock(list(reference_string), num_frames),
    ]
