# Process Scheduling + Memory Management Simulator

A Python simulator for two core OS topics, in one project:

1. **Process scheduling** — FCFS, SJF, SRTF, Round Robin, Priority (preemptive + non-preemptive)
2. **Memory management** — paging, page tables, and page replacement: FIFO, LRU, Optimal, LFU, Clock

Plus a **combined simulator** that schedules processes and then runs their page references through shared physical memory in the order they actually ran — so you can see how scheduling and paging interact.

No external dependencies. Python 3.10+ (tested on 3.12).

## Quick start

```bash
python main.py --demo
python -m unittest discover -s tests -v
```

## Run on localhost (web UI)

No install needed — the web server is Python's standard library only.

```bash
python app.py
# or: ./run_local.sh        (Mac / Linux)
# or: run_local.bat         (Windows)
```

Then open **http://..........** in your browser.

The page is a responsive, mobile-friendly site with a dark-mode toggle and a colour picker in the header — Teal (the new default), Indigo, Emerald, Sunset, Rose, and Ocean. Tap a colour dot and the whole site changes: hero gradient, buttons, accents, and highlights, saved in your browser. It's written like a person, not a manual. It greets you by time of day, walks you through the idea in 3 friendly steps, explains every result in plain English (“here's who waited longest, and why”), and has an OS guide at the bottom that answers questions like “What is a page fault?” and “Why is SJF usually fastest?” in everyday words.

UX highlights: one-tap preset stories (“One very long job”, “Thrashing — too many pages”), sliders for quantum and frames with live values, step-by-step players that play the Gantt chart and the page-replacement trace one step at a time, toast confirmations, copy / download JSON for any result, a recent-runs history saved in your browser, skeleton loading, keyboard focus styles, a skip link, and reduced-motion support. Edit processes, run scheduling with a colour Gantt chart and stat cards, compare all algorithms side by side, compare page-replacement algorithms with visual frame boxes and a step-by-step trace, translate logical addresses, and run the combined simulator — all in the browser, with no data leaving your machine.

Change the port if 8000 is busy:

```bash
python app.py --port 8080

```



### Local API

| Endpoint | Method | What it does |
|----------|--------|--------------|
| `/api/health` | GET | `{"ok": true}` |
| `/api/demo` | GET | Demo processes + all scheduling / replacement results |
| `/api/paging?address=19986&page_size=4096` | GET | Logical → page + offset |
| `/api/scheduling` | POST | `{"processes": [...], "algorithm": "sjf", "quantum": 2}` |
| `/api/replacement` | POST | `{"reference_string": [...], "frames": 3, "algorithm": "lru"}` — use `"all"` to compare |
| `/api/combined` | POST | `{"processes": [...], "algorithm": "sjf", "replacement": "lru", "frames": 4}` |

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/replacement \
  -H 'Content-Type: application/json' \
  -d '{"algorithm": "lru", "frames": 3}'
```

## Usage

```bash
# Interactive menu
python main.py

# Full demo: all scheduling algorithms + all replacement algorithms
python main.py --demo

# Scheduling only
python main.py --sched fcfs
python main.py --sched sjf
python main.py --sched srtf
python main.py --sched rr --quantum 3
python main.py --sched priority

# Page replacement only (classic reference string, 3 frames by default)
python main.py --replace lru --frames 3
python main.py --replace all --frames 4
python main.py --replace fifo --frames 3 --refs 7,0,1,2,0,3,0,4,2,3,0,3,2

# Combined: schedule with SJF, then page with LRU
python main.py --combined --sched sjf --replace lru --frames 4 --quantum 2
# Try --sched rr --frames 3 too: it thrashes (100% page faults) on the demo data

# Paging: translate a logical address
python main.py --paging 19986 --page-size 4096
# Logical 19986 -> page 4, offset 3602
```

## Project structure

```
main.py                     CLI + interactive menu + demo
app.py                      Localhost web server (stdlib only) - http://127.0.0.1:8000
run_local.sh / run_local.bat  Start the localhost server
web/
  index.html                Browser UI: scheduling, replacement, paging, combined
simulator/
  __init__.py
  process.py                Process model, Gantt segments, ScheduleResult + metrics
  scheduling.py             FCFS, SJF, SRTF, Round Robin, Priority
  page_replacement.py       FIFO, LRU, Optimal, LFU, Clock + step-by-step trace
  memory.py                 Paging, PageTable, MemoryManager (shared frames)
  simulator.py              CombinedSimulator, demo processes, comparisons
tests/
  test_simulator.py         13 tests, including the textbook results
  test_localhost.py         6 tests for the localhost server / API
```

## What it computes

**Scheduling, per process:** start, finish, waiting, turnaround, and response time.
Averages, throughput, and CPU utilization are reported too.

**Page replacement, per run:** faults, hits, hit/fault rate, and a full trace table showing frame contents and evictions after every reference.

**Paging:** logical address → page number + offset, page table with valid/reference/modified bits, and physical address from a frame number.

## Verified textbook results

Reference string `7,0,1,2,0,3,0,4,2,3,0,3,2,1,2,0,1,7,0,1` with 3 frames:

| Algorithm | Page faults |
|-----------|-------------|
| FIFO      | 15 |
| LRU       | 12 |
| Optimal   | 9 |

These are asserted in `tests/test_simulator.py`.

Demo processes (arrival, burst, priority):

| PID | Arrival | Burst | Priority |
|-----|---------|-------|----------|
| P1  | 0       | 8     | 2 |
| P2  | 1       | 4     | 1 |
| P3  | 2       | 9     | 3 |
| P4  | 3       | 5     | 2 |

FCFS on these gives average waiting time 8.75 and average turnaround 15.25.

## Use it as a library

```python
from simulator import Process, run, simulate, CombinedSimulator

procs = [Process("P1", 0, 8, 2), Process("P2", 1, 4, 1)]
result = run(procs, "sjf")
print(result.table())
print(result.gantt_chart())

print(simulate([7, 0, 1, 2, 0, 3], 3, "lru").summary())

combined = CombinedSimulator(num_frames=3, replacement="lru").run(procs, "rr", quantum=2)
print(combined.summary())
```

## Notes / limits

- Optimal replacement is offline: it looks ahead in the reference string, so it is only available in `page_replacement.simulate()`. The online `MemoryManager` falls back to LRU for `optimal`.
- The combined simulator issues one page reference per unit of CPU time, cycling through each process's reference string. That is a modelling choice, not a real OS trace.
- All scheduling is in integer time units.
