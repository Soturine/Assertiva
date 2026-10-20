import json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from pact import Verifier

p = json.loads(Path("pacts/orders-web-pricing-api.json").read_text())
p["interactions"][0]["pending"] = True
Path("pacts/pending").mkdir(exist_ok=True)
Path("pacts/pending/orders-web-pricing-api.json").write_text(json.dumps(p, indent=2))

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/discount"):
            body = b'{"discount": "1500"}'
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(body)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass

server = HTTPServer(("127.0.0.1", 0), H)
threading.Thread(target=server.serve_forever, daemon=True).start()
v = Verifier("pricing-api", host="127.0.0.1").add_transport(url=f"http://127.0.0.1:{server.server_port}").add_source("pacts/pending/orders-web-pricing-api.json")
try:
    v.verify(); print("pending verify ok")
except Exception as exc:
    print("pending verify raised", type(exc).__name__)
Path("verification-pending.json").write_text(json.dumps(v.results, indent=2))
d = v.results
print(d["result"], len(d["errors"]), len(d["pendingErrors"]), [r.get("pending") for r in d["interactionResults"]], [r.get("result") for r in d["interactionResults"]])
