import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from madscience_agents import orchestrate


class MadScienceHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/orchestrate":
            self.send_error(404, "Not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            self._send_json(200, orchestrate(payload))
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
        except Exception:
            self._send_json(500, {"error": "The orchestrator could not process this request."})

    def _send_json(self, status, body):
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    port = 4173
    server = ThreadingHTTPServer(("127.0.0.1", port), MadScienceHandler)
    print(f"MadScience Experiments running at http://127.0.0.1:{port}/")
    server.serve_forever()
