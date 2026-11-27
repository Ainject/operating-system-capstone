#!/usr/bin/env python3


from __future__ import annotations

import argparse
import sys

from simulator.memory import physical_address, translate
from simulator.page_replacement import compare_all, simulate
from simulator.process import Process
from simulator.scheduling import run
from simulator.simulator import (
    CLASSIC_REFERENCE_STRING,
    CombinedSimulator,
    compare_scheduling,
    demo_processes,
)


def _print_header(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def show_scheduling(processes, algorithm: str, quantum: int = 2) -> None:
    result = run(processes, algorithm, quantum=quantum)
    _print_header(f"Scheduling: {result.algorithm}")
    print(result.gantt_chart())
    print()
    print(result.table())


def show_replacement(ref: list[int], frames: int, algorithm: str) -> None:
    if algorithm == "all":
        _print_header(f"Page replacement comparison - {frames} frames")
        print(f"Reference string: {ref}\n")
        for r in compare_all(ref, frames):
            print(r.summary())
        print("\nBest (fewest faults): "
              f"{min(compare_all(ref, frames), key=lambda r: r.faults).algorithm}")
        return
    result = simulate(ref, frames, algorithm)
    _print_header(f"Page replacement: {result.algorithm} - {frames} frames")
    print(f"Reference string: {ref}\n")
    print(result.trace_table())


def show_combined(processes, algorithm: str, replacement: str, frames: int, quantum: int = 2) -> None:
    sim = CombinedSimulator(num_frames=frames, replacement=replacement)
    result = sim.run(processes, algorithm, quantum=quantum)
    _print_header("Combined simulator: scheduling + paging")
    print(result.schedule.gantt_chart())
    print()
    print(result.schedule.table())
    print()
    print(result.summary())
    if result.memory_log:
        print("\nFirst 10 page faults:")
        for line in result.memory_log[:10]:
            print(f"  {line}")


def demo() -> None:
    processes = demo_processes()
    _print_header("Process Scheduling + Memory Management Simulator - DEMO")
    print("Processes (PID, arrival, burst, priority):")
    for p in processes:
        print(f"  {p.pid}: arrival={p.arrival_time}, burst={p.burst_time}, "
              f"priority={p.priority}, pages={p.page_references}")

    for result in compare_scheduling(processes, quantum=2):
        print(f"\n{result.algorithm}: avg waiting {result.avg_waiting_time:.2f}, "
              f"avg turnaround {result.avg_turnaround_time:.2f}, "
              f"CPU {result.cpu_utilization:.0f}%")
        print(f"  Gantt: {' | '.join(str(s) for s in result.gantt)}")

    show_replacement(CLASSIC_REFERENCE_STRING, 3, "all")

    print("\nPaging example: logical address 19986, page size 4096")
    page, offset = translate(19986, 4096)
    print(f"  Page {page}, offset {offset} -> physical "
          f"{physical_address(3, offset, 4096)} if page {page} is in frame 3")

    # SJF + 4 frames shows hits; try RR + 3 frames to see thrashing (100% faults)
    show_combined(processes, "sjf", "lru", 4, quantum=2)


def interactive() -> None:
    processes = demo_processes()
    while True:
        print("\n--- Process Scheduling + Memory Management Simulator ---")
        print("1. Scheduling demo (all algorithms)")
        print("2. Page replacement demo (all algorithms, 3 frames)")
        print("3. Combined simulator (RR + LRU, 3 frames)")
        print("4. Full demo")
        print("5. Paging: translate a logical address")
        print("0. Exit")
        choice = input("Choose: ").strip()
        if choice == "1":
            for r in compare_scheduling(processes, quantum=2):
                print(f"\n{r.algorithm}")
                print(r.gantt_chart())
                print(r.table())
        elif choice == "2":
            show_replacement(CLASSIC_REFERENCE_STRING, 3, "all")
        elif choice == "3":
            show_combined(processes, "rr", "lru", 3, quantum=2)
        elif choice == "4":
            demo()
        elif choice == "5":
            try:
                addr = int(input("Logical address: "))
                size = int(input("Page size (power of 2, e.g. 4096): "))
                page, offset = translate(addr, size)
                print(f"Page {page}, offset {offset}")
            except ValueError as e:
                print(f"Error: {e}")
        elif choice == "0":
            print("Goodbye!")
            break
        else:
            print("Invalid choice, try again.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Process Scheduling + Memory Management Simulator")
    parser.add_argument("--demo", action="store_true", help="Run the full demo")
    parser.add_argument("--sched", choices=["fcfs", "sjf", "srtf", "rr", "priority"],
                        help="Scheduling algorithm to run")
    parser.add_argument("--quantum", type=int, default=2, help="Time quantum for Round Robin")
    parser.add_argument("--replace", choices=["fifo", "lru", "optimal", "lfu", "clock", "all"],
                        help="Page replacement algorithm to run")
    parser.add_argument("--frames", type=int, default=3, help="Number of memory frames")
    parser.add_argument("--combined", action="store_true",
                        help="Run scheduling + paging together")
    parser.add_argument("--paging", type=int, help="Translate this logical address")
    parser.add_argument("--page-size", type=int, default=4096, help="Page size in bytes")
    parser.add_argument("--refs", type=str,
                        help="Comma-separated page reference string, e.g. 7,0,1,2,0,3")
    args = parser.parse_args(argv)

    processes = demo_processes()
    refs = ([int(x) for x in args.refs.split(",")] if args.refs
            else CLASSIC_REFERENCE_STRING)

    if args.demo:
        demo()
        return 0
    if args.paging is not None:
        page, offset = translate(args.paging, args.page_size)
        print(f"Logical {args.paging} -> page {page}, offset {offset}")
        print(f"If page {page} is in frame 3: physical "
              f"{physical_address(3, offset, args.page_size)}")
        return 0
    if args.combined:
        show_combined(processes, args.sched or "fcfs", args.replace or "lru",
                      args.frames, quantum=args.quantum)
        return 0
    if args.sched:
        show_scheduling(processes, args.sched, quantum=args.quantum)
        return 0
    if args.replace:
        show_replacement(refs, args.frames, args.replace)
        return 0

    interactive()
    return 0


if __name__ == "__main__":
    sys.exit(main())
