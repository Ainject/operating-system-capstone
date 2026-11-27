#!/usr/bin/env python3
"""Localhost web UI for the Process Scheduling + Memory Management Simulator.

Stdlib only - no Flask, no pip install needed.

Run:
  python app.py                 # http://127.0.0.1:8000
  python app.py --port 8080     # another port
  python app.py --host 0.0.0.0  # listen on all interfaces (only if you need LAN access)

Then open http://127.0.0.1:8000 in your browser.
Press Ctrl+C to stop.
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"
sys.path.insert(0, str(BASE_DIR))

from simulator.memory import physical_address, translate  # noqa: E402
from simulator.page_replacement import compare_all, simulate  # noqa: E402
from simulator.process import Process  # noqa: E402
from simulator.scheduling import run as run_scheduling  # noqa: E402
from simulator.simulator import (  # noqa: E402
    CLASSIC_REFERENCE_STRING,
    CombinedSimulator,
    compare_scheduling,
    demo_processes,
)


def _processes_from(data: list[dict]) -> list[Process]:
    procs = []
    for item in data:
        refs = item.get("page_references") or item.get("pages") or []
        procs.append(Process(
            pid=str(item.get("pid", f"P{len(procs) + 1}")),
            arrival_time=int(item.get("arrival_time", item.get("arrival", 0))),
            burst_time=int(item.get("burst_time", item.get("burst", 0))),
            priority=int(item.get("priority", 1)),
            page_references=[int(x) for x in refs],
        ))
    return procs


def _schedule_json(result) -> dict:
    return {
        "algorithm": result.algorithm,
        "total_time": result.total_time,
        "avg_waiting_time": round(result.avg_waiting_time, 2),
        "avg_turnaround_time": round(result.avg_turnaround_time, 2),
        "avg_response_time": round(result.avg_response_time, 2),
        "throughput": round(result.throughput, 3),
        "cpu_utilization": round(result.cpu_utilization, 1),
        "gantt": [{"pid": s.pid, "start": s.start, "end": s.end} for s in result.gantt],
        "processes": [
            {
                "pid": p.pid, "arrival_time": p.arrival_time, "burst_time": p.burst_time,
                "priority": p.priority, "start_time": p.start_time,
                "completion_time": p.completion_time, "waiting_time": p.waiting_time,
                "turnaround_time": p.turnaround_time, "response_time": p.response_time,
            }
            for p in result.processes
        ],
    }


def _replacement_json(result) -> dict:
    return {
        "algorithm": result.algorithm,
        "num_frames": result.num_frames,
        "reference_string": result.reference_string,
        "faults": result.faults,
        "hits": result.hits,
        "hit_ratio": round(result.hit_ratio, 3),
        "fault_ratio": round(result.fault_ratio, 3),
        "steps": [
            {"page": s.page, "fault": s.fault, "frames": s.frames, "evicted": s.evicted}
            for s in result.steps
        ],
    }


def _demo_json() -> dict:
    processes = demo_processes()
    return {
        "processes": [
            {"pid": p.pid, "arrival_time": p.arrival_time, "burst_time": p.burst_time,
             "priority": p.priority, "page_references": p.page_references}
            for p in processes
        ],
        "scheduling": [_schedule_json(r) for r in compare_scheduling(processes, quantum=2)],
        "replacement": [_replacement_json(r) for r in compare_all(CLASSIC_REFERENCE_STRING, 3)],
        "reference_string": CLASSIC_REFERENCE_STRING,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, fmt, *args):  # keep the console quiet
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode() or "{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            return self._send_json({"ok": True})
        if parsed.path == "/api/demo":
            return self._send_json(_demo_json())
        if parsed.path == "/api/paging":
            q = parse_qs(parsed.query)
            try:
                address = int(q.get("address", ["19986"])[0])
                page_size = int(q.get("page_size", ["4096"])[0])
                page, offset = translate(address, page_size)
                return self._send_json({
                    "address": address, "page_size": page_size,
                    "page": page, "offset": offset,
                    "physical_if_frame_3": physical_address(3, offset, page_size),
                })
            except (ValueError, TypeError) as e:
                return self._send_json({"error": str(e)}, status=400)
        if parsed.path in ("/", "/index.html"):
            return super().do_GET()
        # Any other static file under web/
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            data = self._read_json()
        except Exception as e:
            return self._send_json({"error": f"Invalid JSON: {e}"}, status=400)
        try:
            if parsed.path == "/api/scheduling":
                processes = _processes_from(data.get("processes") or [])
                if not processes:
                    processes = demo_processes()
                result = run_scheduling(
                    processes,
                    data.get("algorithm", "fcfs"),
                    quantum=int(data.get("quantum", 2)),
                    preemptive_priority=bool(data.get("preemptive_priority", False)),
                )
                return self._send_json(_schedule_json(result))

            if parsed.path == "/api/replacement":
                refs = [int(x) for x in (data.get("reference_string") or CLASSIC_REFERENCE_STRING)]
                frames = int(data.get("frames", 3))
                algo = str(data.get("algorithm", "all")).lower()
                if algo == "all":
                    return self._send_json(
                        [_replacement_json(r) for r in compare_all(refs, frames)])
                return self._send_json(_replacement_json(simulate(refs, frames, algo)))

            if parsed.path == "/api/combined":
                processes = _processes_from(data.get("processes") or [])
                if not processes:
                    processes = demo_processes()
                sim = CombinedSimulator(
                    num_frames=int(data.get("frames", 4)),
                    replacement=str(data.get("replacement", "lru")),
                )
                result = sim.run(
                    processes,
                    data.get("algorithm", "sjf"),
                    quantum=int(data.get("quantum", 2)),
                )
                return self._send_json({
                    "schedule": _schedule_json(result.schedule),
                    "num_frames": result.num_frames,
                    "replacement": result.replacement,
                    "total_faults": result.total_faults,
                    "total_hits": result.total_hits,
                    "per_process_faults": result.per_process_faults,
                    "per_process_hits": result.per_process_hits,
                    "memory_log": result.memory_log,
                })
            return self._send_json({"error": f"Unknown API path: {parsed.path}"}, status=404)
        except (ValueError, KeyError, TypeError) as e:
            return self._send_json({"error": str(e)}, status=400)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the simulator on localhost")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port (default 8000)")
    args = parser.parse_args(argv)

    if not (WEB_DIR / "index.html").exists():
        print(f"Missing web UI: {WEB_DIR / 'index.html'}", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Simulator running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
