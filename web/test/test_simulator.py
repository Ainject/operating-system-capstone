"""Tests for the scheduling + memory simulator. Run: python -m unittest discover -s tests -v"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulator.memory import MemoryManager, translate
from simulator.page_replacement import compare_all, simulate
from simulator.process import Process
from simulator.scheduling import fcfs, priority, round_robin, sjf, srtf
from simulator.simulator import CLASSIC_REFERENCE_STRING, CombinedSimulator, demo_processes


def procs():
    return [
        Process("P1", arrival_time=0, burst_time=8, priority=2),
        Process("P2", arrival_time=1, burst_time=4, priority=1),
        Process("P3", arrival_time=2, burst_time=9, priority=3),
        Process("P4", arrival_time=3, burst_time=5, priority=2),
    ]


class TestScheduling(unittest.TestCase):
    def test_fcfs_order_and_avg_wait(self):
        r = fcfs(procs())
        self.assertEqual([s.pid for s in r.gantt], ["P1", "P2", "P3", "P4"])
        # Waiting: P1 0, P2 7, P3 10, P4 18 -> avg 8.75
        self.assertAlmostEqual(r.avg_waiting_time, 8.75)
        self.assertAlmostEqual(r.avg_turnaround_time, 15.25)

    def test_sjf_beats_fcfs_on_waiting(self):
        self.assertLess(sjf(procs()).avg_waiting_time, fcfs(procs()).avg_waiting_time)

    def test_srtf_and_rr_complete_all(self):
        for result in (srtf(procs()), round_robin(procs(), quantum=2)):
            self.assertEqual(len(result.processes), 4)
            self.assertTrue(all(p.completion_time is not None for p in result.processes))
            self.assertEqual(result.total_time, 26)  # 8+4+9+5, no idle time

    def test_priority_non_preemptive_picks_p2_first_after_p1(self):
        r = priority(procs())
        # P1 runs first (arrives at 0), then highest priority P2
        self.assertEqual(r.gantt[1].pid, "P2")

    def test_rr_quantum_1_finishes(self):
        r = round_robin(procs(), quantum=1)
        self.assertEqual(r.total_time, 26)


class TestPageReplacement(unittest.TestCase):
    def test_classic_textbook_results_3_frames(self):
        # The standard textbook example: FIFO 15, LRU 12, Optimal 9 faults
        self.assertEqual(simulate(CLASSIC_REFERENCE_STRING, 3, "fifo").faults, 15)
        self.assertEqual(simulate(CLASSIC_REFERENCE_STRING, 3, "lru").faults, 12)
        self.assertEqual(simulate(CLASSIC_REFERENCE_STRING, 3, "optimal").faults, 9)

    def test_all_algorithms_agree_on_total_refs(self):
        for r in compare_all(CLASSIC_REFERENCE_STRING, 3):
            self.assertEqual(r.faults + r.hits, len(CLASSIC_REFERENCE_STRING))

    def test_empty_string(self):
        r = simulate([], 3, "lru")
        self.assertEqual(r.faults, 0)

    def test_more_frames_never_hurts_lru(self):
        self.assertLessEqual(simulate(CLASSIC_REFERENCE_STRING, 4, "lru").faults,
                             simulate(CLASSIC_REFERENCE_STRING, 3, "lru").faults)


class TestPaging(unittest.TestCase):
    def test_translate(self):
        page, offset = translate(19986, 4096)
        self.assertEqual((page, offset), (4, 3602))

    def test_memory_manager_hit_and_fault(self):
        mm = MemoryManager(num_frames=3, replacement="lru")
        mm.create_process("P1", 5)
        hit, _ = mm.access("P1", 1)
        self.assertFalse(hit)
        hit, _ = mm.access("P1", 1)
        self.assertTrue(hit)
        self.assertEqual((mm.faults, mm.hits), (1, 1))

    def test_memory_manager_evicts_with_lru(self):
        mm = MemoryManager(num_frames=2, replacement="lru")
        mm.create_process("P1", 5)
        for page in (1, 2, 1, 3):
            mm.access("P1", page)
        # Page 2 should have been evicted (least recently used)
        hit, _ = mm.access("P1", 2)
        self.assertFalse(hit)


class TestCombined(unittest.TestCase):
    def test_combined_runs(self):
        result = CombinedSimulator(num_frames=3, replacement="lru").run(
            demo_processes(), "rr", quantum=2)
        self.assertGreater(result.total_faults, 0)
        self.assertEqual(result.total_faults + result.total_hits, 26)  # total burst time


if __name__ == "__main__":
    unittest.main()
