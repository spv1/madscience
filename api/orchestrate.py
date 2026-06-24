import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from madscience_agents import orchestrate


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._send_json(200, orchestrate(payload))
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception:
            self._send_json(500, {"error": "The orchestrator could not process this request."})

    def do_GET(self):
        self._send_json(200, {"ok": True, "service": "MadScience Experiments Orchestrator"})
