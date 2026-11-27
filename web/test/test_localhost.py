"""Tests for the localhost web server. Run: python -m unittest discover -s tests -v"""

import json
import sys
import threading
import unittest
import urllib.request
from http.client import HTTPConnection
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import Handler
from http.server import ThreadingHTTPServer


def _request(port, method, path, body=None):
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=json.dumps(body) if body is not None else None, headers=headers)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode())
    conn.close()
    return resp.status, data


class TestLocalhost(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_health(self):
        status, data = _request(self.port, "GET", "/api/health")
        self.assertEqual((status, data), (200, {"ok": True}))

    def test_index_serves_html(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        body = resp.read().decode()
        conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn("Process Scheduling", body)

    def test_paging(self):
        status, data = _request(self.port, "GET", "/api/paging?address=19986&page_size=4096")
        self.assertEqual(status, 200)
        self.assertEqual((data["page"], data["offset"]), (4, 3602))

    def test_scheduling_sjf(self):
        status, data = _request(self.port, "POST", "/api/scheduling", {"algorithm": "sjf"})
        self.assertEqual(status, 200)
        self.assertAlmostEqual(data["avg_waiting_time"], 7.75)

    def test_replacement_lru(self):
        status, data = _request(self.port, "POST", "/api/replacement",
                                {"algorithm": "lru", "frames": 3})
        self.assertEqual(status, 200)
        self.assertEqual(data["faults"], 12)

    def test_combined(self):
        status, data = _request(self.port, "POST", "/api/combined",
                                {"algorithm": "sjf", "replacement": "lru", "frames": 4})
        self.assertEqual(status, 200)
        self.assertEqual(data["total_faults"] + data["total_hits"], 26)


if __name__ == "__main__":
    unittest.main()
